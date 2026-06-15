"""
Task Scheduler Module

Runs a periodic background sweep that recovers documents stuck in
PROCESSING/QUEUED state (e.g. their Celery task died or was purged) and
re-enqueues them. Celery itself (worker_concurrency + prefetch_multiplier)
already handles task distribution and concurrency limits, so there's nothing
else for this scheduler to do.
"""

import asyncio
import logging
from typing import Optional

from prisma import Prisma
from celery import Celery

from app.services.stuck_document_recovery import StuckDocumentRecovery

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Background scheduler that periodically recovers stuck documents."""

    def __init__(
        self,
        db: Optional[Prisma],
        celery_app: Celery,
        health_check_interval: int = 20,
    ):
        self.health_check_interval = health_check_interval
        self.db = db
        self.recovery = StuckDocumentRecovery(db=db, celery_app=celery_app)

        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        logger.info(f"TaskScheduler initialized: interval={health_check_interval}s")

    async def _sync_active_documents_on_startup(self) -> None:
        """Query database for any processing/queued documents and add them to Redis."""
        from app.utils.db_pool import get_prisma_with_pool, connect_prisma_with_timeout, disconnect_prisma_with_timeout
        from app.utils.redis_client import redis_client

        logger.info("[SCHEDULER] Syncing active documents from database on startup...")
        db = get_prisma_with_pool()
        await connect_prisma_with_timeout(db, timeout=30)
        try:
            active_docs = await db.document.find_many(
                where={"status": {"in": ["PENDING", "QUEUED", "PROCESSING"]}}
            )
            if active_docs:
                doc_ids = [doc.id for doc in active_docs]
                logger.info(f"[SCHEDULER] Found {len(doc_ids)} active documents in database on startup. Adding to Redis.")
                await redis_client.sadd("active_documents", *doc_ids)
            else:
                logger.info("[SCHEDULER] No active documents found in database on startup.")
        finally:
            await disconnect_prisma_with_timeout(db, timeout=10)

    async def start(self) -> None:
        if self._running:
            logger.warning("TaskScheduler is already running")
            return

        # Perform startup sync to populate Redis active_documents set from the DB
        try:
            await self._sync_active_documents_on_startup()
        except Exception as e:
            logger.error(f"Failed to sync active documents on startup: {e}", exc_info=True)

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("TaskScheduler started")

    async def stop(self) -> None:
        if not self._running:
            logger.warning("TaskScheduler is not running")
            return

        logger.info("Stopping TaskScheduler...")
        self._running = False

        if self._scheduler_task:
            try:
                await asyncio.wait_for(self._scheduler_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("TaskScheduler did not stop within timeout, cancelling")
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass

        logger.info("TaskScheduler stopped")

    async def _scheduler_loop(self) -> None:
        logger.info(f"[SCHEDULER] Recovery loop started (interval={self.health_check_interval}s)")

        from app.utils.redis_client import redis_client
        from app.utils.db_pool import get_prisma_with_pool, connect_prisma_with_timeout, disconnect_prisma_with_timeout

        while self._running:
            try:
                # 1. Check if there are active documents in Redis
                active_count = await redis_client.scard("active_documents")
                if active_count > 0:
                    logger.info(f"[SCHEDULER] Found {active_count} active documents in Redis. Running recovery sweep.")
                    
                    # Create and connect DB client
                    db = get_prisma_with_pool()
                    await connect_prisma_with_timeout(db, timeout=30)
                    
                    try:
                        self.recovery.db = db
                        result = await self.recovery.recover_stuck_documents()
                        if result.stuck_documents_recovered or result.errors:
                            logger.info(
                                f"[SCHEDULER] Recovery sweep: "
                                f"recovered={result.stuck_documents_recovered}, errors={len(result.errors)}"
                            )
                        for error in result.errors:
                            logger.error(f"[SCHEDULER] Error: {error}")
                    finally:
                        await disconnect_prisma_with_timeout(db, timeout=10)
                else:
                    # No active documents, skip database sweep to allow Neon DB to scale down to 0
                    logger.debug("[SCHEDULER] No active documents in Redis. Skipping database sweep.")
            except Exception as e:
                logger.exception(f"[SCHEDULER] Unexpected error in recovery loop: {e}")

            try:
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                logger.info("[SCHEDULER] Recovery loop cancelled")
                break

        logger.info("[SCHEDULER] Recovery loop stopped")
