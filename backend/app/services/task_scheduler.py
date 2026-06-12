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
        db: Prisma,
        celery_app: Celery,
        health_check_interval: int = 20,
    ):
        self.health_check_interval = health_check_interval
        self.recovery = StuckDocumentRecovery(db=db, celery_app=celery_app)

        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        logger.info(f"TaskScheduler initialized: interval={health_check_interval}s")

    async def start(self) -> None:
        if self._running:
            logger.warning("TaskScheduler is already running")
            return

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

        while self._running:
            try:
                result = await self.recovery.recover_stuck_documents()
                if result.stuck_documents_recovered or result.errors:
                    logger.info(
                        f"[SCHEDULER] Recovery sweep: "
                        f"recovered={result.stuck_documents_recovered}, errors={len(result.errors)}"
                    )
                for error in result.errors:
                    logger.error(f"[SCHEDULER] Error: {error}")
            except Exception as e:
                logger.exception(f"[SCHEDULER] Unexpected error in recovery loop: {e}")

            try:
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                logger.info("[SCHEDULER] Recovery loop cancelled")
                break

        logger.info("[SCHEDULER] Recovery loop stopped")
