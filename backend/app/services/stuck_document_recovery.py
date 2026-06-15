"""
Stuck Document Recovery Module

Celery's own queue + worker_concurrency/prefetch settings already throttle and
distribute document processing tasks, so the application doesn't need to track
queue depth or worker slots itself. The one thing it can't recover from on its
own is a document left in PROCESSING/QUEUED state whose Celery task is gone
(worker crashed, task was revoked, queue was purged on shutdown, etc).
This module periodically finds those documents and re-enqueues them.
"""

from dataclasses import dataclass, field
from typing import List
from datetime import datetime, timedelta, timezone
import logging
import uuid

from celery import Celery
from prisma import Prisma

from app.services.celery_inspector import CeleryInspector
from app.workers.tasks import process_document_task
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RecoveryResult:
    """Result of a stuck-document recovery sweep."""
    stuck_documents_recovered: int = 0
    errors: List[str] = field(default_factory=list)


class StuckDocumentRecovery:
    """Finds documents stuck in PROCESSING/QUEUED with no running Celery task and re-enqueues them."""

    def __init__(self, db: Prisma, celery_app: Celery):
        self.db = db
        self.inspector = CeleryInspector(celery_app)

    async def recover_stuck_documents(self) -> RecoveryResult:
        result = RecoveryResult()

        try:
            stuck_doc_ids = await self._detect_stuck_documents()
        except Exception as e:
            logger.error(f"Stuck document detection failed: {e}", exc_info=True)
            result.errors.append(f"Stuck detection failed: {e}")
            return result

        for doc_id in stuck_doc_ids:
            try:
                await self._recover(doc_id)
                result.stuck_documents_recovered += 1
                logger.info(f"[RECOVERY] Recovered and re-enqueued stuck document {doc_id}")
            except Exception as e:
                logger.error(f"[RECOVERY] Failed to recover document {doc_id}: {e}", exc_info=True)
                result.errors.append(f"Recovery failed for {doc_id}: {e}")

        return result

    async def _detect_stuck_documents(self) -> List[str]:
        """
        A document is stuck if it's PROCESSING/QUEUED, its Celery task isn't
        actively running, and it's been in that state longer than the
        configured threshold (a much shorter threshold for QUEUED documents
        when no workers are active at all).
        """
        from app.utils.redis_client import redis_client

        redis_active_ids = await redis_client.smembers("active_documents")
        if not redis_active_ids:
            return []

        # Find these documents in the database
        processing_docs = await self.db.document.find_many(
            where={"id": {"in": list(redis_active_ids)}},
            include={"job": True}
        )

        db_docs_dict = {doc.id: doc for doc in processing_docs}

        # Self-healing: if a document is in Redis but not in the DB, or is not in PENDING/QUEUED/PROCESSING, remove it from Redis!
        for doc_id in list(redis_active_ids):
            doc = db_docs_dict.get(doc_id)
            if not doc or doc.status not in ("PENDING", "QUEUED", "PROCESSING"):
                logger.info(
                    f"[RECOVERY] Self-healing: removing inactive/missing document {doc_id} "
                    f"(status: {doc.status if doc else 'DELETED'}) from Redis active_documents"
                )
                await redis_client.srem("active_documents", doc_id)

        # Filter processing_docs to only include in-progress states (QUEUED/PROCESSING)
        active_db_docs = [doc for doc in processing_docs if doc.status in ("PROCESSING", "QUEUED")]
        if not active_db_docs:
            return []

        active_tasks = await self.inspector.get_active_tasks()
        active_task_ids = {task['id'] for task in active_tasks}
        no_active_tasks = len(active_task_ids) == 0

        stuck_threshold = datetime.now(timezone.utc) - timedelta(seconds=settings.SCHEDULER_STUCK_THRESHOLD)

        stuck_doc_ids = []
        for doc in active_db_docs:
            if not doc.job:
                continue

            if doc.job.celeryTaskId in active_task_ids:
                continue

            reference_time = doc.job.startedAt if doc.status == "PROCESSING" else doc.job.updatedAt

            threshold = stuck_threshold
            if doc.status == "QUEUED" and no_active_tasks:
                threshold = datetime.now(timezone.utc) - timedelta(seconds=30)

            if reference_time and reference_time < threshold:
                stuck_doc_ids.append(doc.id)
                age = (datetime.now(timezone.utc) - reference_time).total_seconds()
                logger.warning(
                    f"[RECOVERY] Stuck {doc.status} document: "
                    f"doc_id={doc.id}, task_id={doc.job.celeryTaskId}, age={age:.0f}s"
                )

        return stuck_doc_ids

    async def _recover(self, document_id: str) -> None:
        """Reset a stuck document to QUEUED with a fresh task ID and re-enqueue it."""
        document = await self.db.document.find_unique(
            where={"id": document_id},
            include={"job": True}
        )

        if not document or document.status not in ("PROCESSING", "QUEUED") or not document.job:
            logger.debug(f"Document {document_id} already recovered or changed state, skipping")
            return

        task_id = str(uuid.uuid4())

        await self.db.job.update(
            where={"id": document.job.id},
            data={
                "status": "QUEUED",
                "celeryTaskId": task_id,
                "errorMessage": "Recovered from stuck state",
                "failedAt": None,
            }
        )
        await self.db.document.update(where={"id": document_id}, data={"status": "QUEUED"})

        process_document_task.apply_async(args=[document_id, document.filePath], task_id=task_id)
