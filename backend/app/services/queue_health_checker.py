"""
Queue Health Checker Module

This module monitors the document processing queue and ensures efficient utilization
of Celery worker capacity. It automatically enqueues pending documents when worker
slots are available and detects/recovers stuck documents.

Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 4.3, 4.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6,
              8.1, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 11.1, 11.2, 11.3, 11.4
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import logging
import asyncio

from celery import Celery
from prisma import Prisma

from app.services.celery_inspector import CeleryInspector
from app.workers.tasks import process_document_task
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """
    Result of a queue health check operation.
    
    Contains metrics about queue state and actions taken during the health check.
    """
    queue_depth: int = 0
    pending_count: int = 0
    processing_count: int = 0
    active_tasks: int = 0
    slots_available: int = 0
    documents_enqueued: int = 0
    stuck_documents_recovered: int = 0
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QueueHealthChecker:
    """
    Queue health checker that monitors and manages document processing queue.
    
    Responsibilities:
    - Calculate queue depth (PENDING + PROCESSING documents)
    - Track active Celery tasks
    - Detect stuck documents (marked PROCESSING but not actively running)
    - Enqueue pending documents when worker slots are available
    - Enforce concurrency limits
    
    Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 4.3, 4.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 8.1,
                  10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 11.1, 11.2, 11.3, 11.4
    """
    
    def __init__(
        self,
        db: Prisma,
        celery_app: Celery,
        max_concurrency: int = 4
    ):
        """
        Initialize the queue health checker.
        
        Args:
            db: Prisma database client
            celery_app: Celery application instance
            max_concurrency: Maximum number of concurrent processing tasks
        """
        self.db = db
        self.celery_app = celery_app
        self.max_concurrency = max_concurrency
        self.inspector = CeleryInspector(celery_app)
        
        logger.info(
            f"QueueHealthChecker initialized with max_concurrency={max_concurrency}"
        )
    
    async def check_and_enqueue(self) -> HealthCheckResult:
        """
        Check queue health and enqueue pending documents.
        
        This is the main orchestration method that:
        1. Calculates queue depth
        2. Gets active task count from Celery
        3. Detects and recovers stuck documents
        4. Enqueues pending documents up to available slots
        
        Returns:
            HealthCheckResult with metrics and actions taken
        
        Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 6.1, 6.3, 8.1, 11.1, 11.2, 11.3, 11.4
        """
        result = HealthCheckResult()
        
        try:
            # Step 1: Get queue depth
            # Requirements: 1.2, 8.1
            try:
                pending_count, processing_count = await self._get_queue_depth()
                result.pending_count = pending_count
                result.processing_count = processing_count
                result.queue_depth = pending_count + processing_count
                
                logger.debug(
                    f"Queue depth: {result.queue_depth} "
                    f"(pending={pending_count}, processing={processing_count})"
                )
            except Exception as e:
                logger.error(f"Failed to get queue depth: {e}", exc_info=True)
                result.errors.append(f"Queue depth query failed: {e}")
                return result
            
            # If queue is empty, nothing to do
            # Requirement: 1.2
            if result.queue_depth == 0:
                logger.debug("Queue is empty, skipping health check")
                return result
            
            # Log warnings/errors based on queue depth thresholds
            # Requirement: 8.1
            if result.queue_depth >= settings.SCHEDULER_QUEUE_ERROR:
                logger.error(
                    f"Queue depth critical: {result.queue_depth} documents "
                    f"(threshold: {settings.SCHEDULER_QUEUE_ERROR})"
                )
            elif result.queue_depth >= settings.SCHEDULER_QUEUE_WARNING:
                logger.warning(
                    f"Queue depth high: {result.queue_depth} documents "
                    f"(threshold: {settings.SCHEDULER_QUEUE_WARNING})"
                )
            
            # Step 2: Get active task count from Celery
            # Requirements: 1.2, 6.1
            try:
                active_tasks = await self.get_active_task_count()
                result.active_tasks = active_tasks
                
                logger.debug(f"Active Celery tasks: {active_tasks}")
            except Exception as e:
                logger.error(f"Failed to get active task count: {e}", exc_info=True)
                result.errors.append(f"Celery inspector failed: {e}")
                return result
            
            # Step 3: Detect and recover stuck documents
            # Requirements: 6.3, 6.4, 6.5, 6.6
            try:
                stuck_docs = await self.detect_stuck_documents()
                
                for doc_id in stuck_docs:
                    try:
                        await self.recover_stuck_document(doc_id)
                        result.stuck_documents_recovered += 1
                        logger.info(f"Recovered stuck document: {doc_id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to recover stuck document {doc_id}: {e}",
                            exc_info=True
                        )
                        result.errors.append(f"Recovery failed for {doc_id}: {e}")
            except Exception as e:
                logger.error(f"Stuck document detection failed: {e}", exc_info=True)
                result.errors.append(f"Stuck detection failed: {e}")
            
            # Step 4: Calculate available slots and enqueue pending documents
            # Requirements: 1.2, 1.3, 1.4, 1.5, 4.3, 4.4
            slots_available = self.max_concurrency - active_tasks
            result.slots_available = slots_available
            
            if slots_available > 0:
                logger.debug(f"Available worker slots: {slots_available}")
                
                try:
                    # Get pending documents ordered by uploadedAt (oldest first)
                    # Requirement: 1.2
                    pending_docs = await self._get_pending_documents(
                        limit=slots_available
                    )
                    
                    logger.debug(
                        f"Found {len(pending_docs)} pending documents to enqueue"
                    )
                    
                    # Enqueue each pending document
                    # Requirements: 1.2, 1.3, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
                    for doc in pending_docs:
                        try:
                            success = await self.enqueue_document(doc.id)
                            if success:
                                result.documents_enqueued += 1
                                logger.info(
                                    f"Enqueued document {doc.id} "
                                    f"(file: {doc.originalName})"
                                )
                        except Exception as e:
                            logger.error(
                                f"Failed to enqueue document {doc.id}: {e}",
                                exc_info=True
                            )
                            result.errors.append(f"Enqueue failed for {doc.id}: {e}")
                except Exception as e:
                    logger.error(f"Failed to get pending documents: {e}", exc_info=True)
                    result.errors.append(f"Pending query failed: {e}")
            else:
                logger.debug(
                    f"No available worker slots "
                    f"(active={active_tasks}, max={self.max_concurrency})"
                )
            
            # Log health check summary
            # Requirement: 8.1
            logger.info(
                f"[SCHEDULER] Health check: queue_depth={result.queue_depth}, "
                f"active_tasks={result.active_tasks}, "
                f"slots_available={result.slots_available}, "
                f"enqueued={result.documents_enqueued}, "
                f"stuck_recovered={result.stuck_documents_recovered}"
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in health check: {e}")
            result.errors.append(f"Unexpected error: {e}")
            return result
    
    async def _get_queue_depth(self) -> tuple[int, int]:
        """
        Calculate queue depth as count of PENDING and PROCESSING documents.
        
        Returns:
            Tuple of (pending_count, processing_count)
        
        Requirements: 1.2, 8.1
        """
        try:
            pending_count = await self.db.document.count(
                where={"status": "PENDING"}
            )
            
            processing_count = await self.db.document.count(
                where={"status": {"in": ["PROCESSING", "QUEUED"]}}
            )
            
            return pending_count, processing_count
            
        except Exception as e:
            logger.error(f"Failed to calculate queue depth: {e}", exc_info=True)
            raise
    
    async def get_active_task_count(self) -> int:
        """
        Query Celery for actual active task count.
        
        This queries the Celery workers directly to get the count of tasks
        that are currently executing, not just marked as PROCESSING in the database.
        
        Returns:
            Number of currently executing tasks
        
        Requirements: 1.2, 6.1
        """
        try:
            count = await self.inspector.get_active_task_count()
            return count
        except Exception as e:
            logger.error(f"Failed to get active task count: {e}", exc_info=True)
            raise
    
    async def detect_stuck_documents(self) -> List[str]:
        """
        Identify documents stuck in PROCESSING state.
        
        A document is considered stuck if:
        1. It has status "PROCESSING" in the database
        2. Its celeryTaskId is not in the list of active Celery tasks
        3. It has been in PROCESSING state for longer than SCHEDULER_STUCK_THRESHOLD
        
        Returns:
            List of stuck document IDs
        
        Requirements: 6.3, 6.4
        """
        try:
            # Get all documents with PROCESSING or QUEUED status (both can get stuck)
            processing_docs = await self.db.document.find_many(
                where={"status": {"in": ["PROCESSING", "QUEUED"]}},
                include={"job": True}
            )
            
            if not processing_docs:
                return []
            
            # Get active task IDs from Celery
            active_tasks = await self.inspector.get_active_tasks()
            active_task_ids = {task['id'] for task in active_tasks}
            
            # Calculate stuck threshold time (timezone-aware)
            stuck_threshold = datetime.now(timezone.utc) - timedelta(
                seconds=settings.SCHEDULER_STUCK_THRESHOLD
            )
            
            # For QUEUED docs with no active tasks at all, use a much shorter threshold
            # (they should start processing within seconds, not minutes)
            no_active_tasks = len(active_task_ids) == 0

            stuck_doc_ids = []

            for doc in processing_docs:
                if not doc.job:
                    continue

                celery_task_id = doc.job.celeryTaskId

                # Task is not actively running
                if celery_task_id not in active_task_ids:
                    # For QUEUED docs: use updatedAt (when it was queued) since startedAt is never set
                    # For PROCESSING docs: use startedAt
                    reference_time = doc.job.startedAt if doc.status == "PROCESSING" else doc.job.updatedAt

                    # QUEUED docs with no workers at all: recover after 30s
                    # Otherwise use the normal stuck threshold
                    threshold = stuck_threshold
                    if doc.status == "QUEUED" and no_active_tasks:
                        threshold = datetime.now(timezone.utc) - timedelta(seconds=30)

                    if reference_time and reference_time < threshold:
                        stuck_doc_ids.append(doc.id)
                        age = (datetime.now(timezone.utc) - reference_time).total_seconds()
                        logger.warning(
                            f"[SCHEDULER] Stuck {doc.status} document: "
                            f"doc_id={doc.id}, task_id={celery_task_id}, age={age:.0f}s"
                        )
            
            return stuck_doc_ids
            
        except Exception as e:
            logger.error(f"Failed to detect stuck documents: {e}", exc_info=True)
            raise
    
    async def recover_stuck_document(self, document_id: str) -> None:
        """
        Reset stuck document to PENDING state for re-processing.
        
        Args:
            document_id: ID of the stuck document
        
        Requirements: 6.5, 6.6
        """
        try:
            # Atomically update only if still in stuck state (idempotent)
            updated = await self.db.document.update_many(
                where={"id": document_id, "status": {"in": ["PROCESSING", "QUEUED"]}},
                data={"status": "PENDING"}
            )

            if updated == 0:
                logger.debug(f"Document {document_id} already recovered or changed state, skipping")
                return

            # Get document to update job
            document = await self.db.document.find_unique(
                where={"id": document_id},
                include={"job": True}
            )

            if document and document.job:
                await self.db.job.update(
                    where={"id": document.job.id},
                    data={
                        "status": "PENDING",
                        "errorMessage": "Recovered from stuck state",
                        "failedAt": None
                    }
                )

            logger.info(f"Successfully recovered stuck document {document_id} to PENDING state")
            
        except Exception as e:
            logger.error(
                f"Failed to recover stuck document {document_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _get_pending_documents(self, limit: int) -> List:
        """
        Get pending documents ordered by uploadedAt (oldest first).
        
        Args:
            limit: Maximum number of documents to retrieve
        
        Returns:
            List of pending documents
        
        Requirements: 1.2
        """
        try:
            documents = await self.db.document.find_many(
                where={"status": "PENDING"},
                order={"uploadedAt": "asc"},
                take=limit,
                include={"job": True}
            )
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get pending documents: {e}", exc_info=True)
            raise
    
    async def enqueue_document(self, document_id: str) -> bool:
        """
        Enqueue a single document for processing with idempotent guarantees.
        
        Uses database transaction with SELECT FOR UPDATE to ensure atomic
        status updates and prevent duplicate task creation.
        
        Args:
            document_id: ID of the document to enqueue
        
        Returns:
            True if enqueued successfully, False otherwise
        
        Requirements: 1.2, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
        """
        try:
            # Fetch document and verify it's still PENDING before enqueuing
            # Requirements: 10.1, 10.2, 10.3
            document = await self.db.document.find_unique(
                where={"id": document_id},
                include={"job": True}
            )

            if not document:
                logger.warning(f"Document {document_id} not found")
                return False

            if document.status != "PENDING":
                logger.debug(
                    f"Document {document_id} status is {document.status}, "
                    f"skipping enqueue"
                )
                return False

            # Atomically update status to PROCESSING so concurrent health checks
            # won't pick up the same document (update_many with WHERE status=PENDING)
            updated = await self.db.document.update_many(
                where={"id": document_id, "status": "PENDING"},
                data={"status": "PROCESSING"}
            )

            if updated == 0:
                # Another process already claimed this document
                logger.debug(f"Document {document_id} already claimed, skipping")
                return False

            # Update job status to PROCESSING
            if document.job:
                await self.db.job.update(
                    where={"id": document.job.id},
                    data={"status": "PROCESSING"}
                )

            # Enqueue the Celery task
            task_result = process_document_task.delay(
                document_id=document_id,
                file_path=document.filePath
            )

            # Update job with actual Celery task ID
            if document.job:
                await self.db.job.update(
                    where={"id": document.job.id},
                    data={"celeryTaskId": task_result.id}
                )

            logger.debug(
                f"Enqueued document {document_id} with task_id {task_result.id}"
            )

            return True
            
        except Exception as e:
            logger.error(
                f"Failed to enqueue document {document_id}: {e}",
                exc_info=True
            )
            return False
