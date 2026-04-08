"""
Task Scheduler Module

This module implements a background scheduler that periodically checks queue health
and automatically enqueues pending documents when worker slots are available.
It also supports immediate health check triggers after document operations.

Requirements: 1.1, 2.5, 2.6, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 11.5, 11.6
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime

from prisma import Prisma
from celery import Celery

from app.services.queue_health_checker import QueueHealthChecker, HealthCheckResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Background task scheduler that monitors queue health and enqueues pending documents.
    
    The scheduler runs a periodic health check loop at a configurable interval
    (default: 20 seconds) and also supports immediate triggers after document
    operations that free up worker slots.
    
    Requirements: 1.1, 2.5, 2.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
    """
    
    def __init__(
        self,
        db: Prisma,
        celery_app: Celery,
        health_check_interval: int = 20,
        max_concurrency: int = 4
    ):
        """
        Initialize the task scheduler.
        
        Args:
            db: Prisma database client
            celery_app: Celery application instance
            health_check_interval: Seconds between periodic health checks (default: 20)
            max_concurrency: Maximum number of concurrent processing tasks (default: 4)
        
        Requirements: 9.1 - Initialize scheduler with configuration
        """
        self.db = db
        self.celery_app = celery_app
        self.health_check_interval = health_check_interval
        self.max_concurrency = max_concurrency
        
        # Initialize queue health checker
        self.health_checker = QueueHealthChecker(
            db=db,
            celery_app=celery_app,
            max_concurrency=max_concurrency
        )
        
        # Scheduler state
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._immediate_check_pending = False
        self._immediate_check_lock = asyncio.Lock()
        # Shared lock prevents periodic and immediate checks from running simultaneously
        self._health_check_running = False
        self._health_check_lock = asyncio.Lock()
        
        logger.info(
            f"TaskScheduler initialized: "
            f"health_check_interval={health_check_interval}s, "
            f"max_concurrency={max_concurrency}"
        )
    
    async def start(self) -> None:
        """
        Start the background scheduler loop.
        
        Creates a background asyncio task that runs the periodic health check loop.
        This method returns immediately without blocking.
        
        Requirements: 9.1, 9.2 - Start scheduler automatically when application starts
        """
        if self._running:
            logger.warning("TaskScheduler is already running")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info("TaskScheduler started")
    
    async def stop(self) -> None:
        """
        Stop the scheduler gracefully.
        
        Signals the scheduler loop to stop and waits for the current health check
        to complete before returning.
        
        Requirements: 9.2, 9.4 - Stop scheduler when application shuts down,
                                 complete current check before stopping
        """
        if not self._running:
            logger.warning("TaskScheduler is not running")
            return
        
        logger.info("Stopping TaskScheduler...")
        self._running = False
        
        # Wait for scheduler task to complete
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
    
    async def trigger_immediate_check(self) -> None:
        """
        Trigger an immediate health check (non-blocking).
        
        This method is called after document operations (delete, cancel, retry)
        to immediately check for pending documents without waiting for the next
        periodic interval. It uses debouncing to prevent multiple simultaneous checks.
        
        The method returns immediately without blocking the caller. The actual
        health check runs in the background.
        
        Requirements: 2.5, 2.6 - Trigger immediate check after operations,
                                 don't interfere with periodic schedule
        """
        # Use lock to prevent multiple simultaneous immediate checks
        async with self._immediate_check_lock:
            if self._immediate_check_pending:
                logger.debug("Immediate check already pending, skipping")
                return
            
            self._immediate_check_pending = True
            logger.debug("Immediate health check triggered")
            
            # Create background task for immediate check
            asyncio.create_task(self._run_immediate_check())
    
    async def _run_immediate_check(self) -> None:
        """Internal method to run an immediate health check."""
        try:
            # Use shared lock so immediate and periodic checks don't race
            async with self._health_check_lock:
                result = await self.health_checker.check_and_enqueue()

            logger.info(
                f"[SCHEDULER] Immediate check: queue_depth={result.queue_depth}, "
                f"active_tasks={result.active_tasks}, "
                f"slots_available={result.slots_available}, "
                f"enqueued={result.documents_enqueued}, "
                f"stuck_recovered={result.stuck_documents_recovered}"
            )

            if result.errors:
                logger.warning(f"[SCHEDULER] Immediate check completed with {len(result.errors)} errors")
                for error in result.errors:
                    logger.error(f"[SCHEDULER] Error: {error}")

        except Exception as e:
            logger.exception(f"[SCHEDULER] Immediate check failed: {e}")

        finally:
            async with self._immediate_check_lock:
                self._immediate_check_pending = False
    
    async def _scheduler_loop(self) -> None:
        """
        Internal periodic health check loop.
        
        Runs continuously while the scheduler is active, executing health checks
        at the configured interval. Includes comprehensive error handling to
        prevent loop crashes.
        
        Requirements: 1.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.3, 9.5, 11.5, 11.6
        """
        logger.info(
            f"[SCHEDULER] Periodic health check loop started "
            f"(interval={self.health_check_interval}s)"
        )
        
        consecutive_errors = 0
        last_error_summary_time = datetime.now()
        
        while self._running:
            try:
                # Use shared lock so periodic and immediate checks don't race
                async with self._health_check_lock:
                    result = await self.health_checker.check_and_enqueue()
                
                # Reset consecutive error count on success
                if not result.errors:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                
                # Log health check summary
                # Requirement: 8.2, 8.5, 8.6
                logger.info(
                    f"[SCHEDULER] Health check: queue_depth={result.queue_depth}, "
                    f"active_tasks={result.active_tasks}, "
                    f"slots_available={result.slots_available}, "
                    f"enqueued={result.documents_enqueued}, "
                    f"stuck_recovered={result.stuck_documents_recovered}"
                )
                
                # Log queue depth warnings/errors
                # Requirements: 8.3, 8.4
                if result.queue_depth >= settings.SCHEDULER_QUEUE_ERROR:
                    logger.error(
                        f"[SCHEDULER] Queue depth critical: {result.queue_depth} documents "
                        f"(threshold: {settings.SCHEDULER_QUEUE_ERROR})"
                    )
                elif result.queue_depth >= settings.SCHEDULER_QUEUE_WARNING:
                    logger.warning(
                        f"[SCHEDULER] Queue depth high: {result.queue_depth} documents "
                        f"(threshold: {settings.SCHEDULER_QUEUE_WARNING})"
                    )
                
                # Log errors if any
                if result.errors:
                    logger.warning(
                        f"[SCHEDULER] Health check completed with {len(result.errors)} errors"
                    )
                    for error in result.errors:
                        logger.error(f"[SCHEDULER] Error: {error}")
                
                # Log error summary every 5 minutes if errors persist
                # Requirement: 11.6
                if consecutive_errors > 0:
                    time_since_last_summary = (datetime.now() - last_error_summary_time).total_seconds()
                    if time_since_last_summary >= 300:  # 5 minutes
                        logger.error(
                            f"[SCHEDULER] Error summary: {consecutive_errors} consecutive "
                            f"health checks with errors in the last 5 minutes"
                        )
                        last_error_summary_time = datetime.now()
            
            except Exception as e:
                # Catch-all error handler to prevent loop crashes
                # Requirement: 11.5
                consecutive_errors += 1
                logger.exception(f"[SCHEDULER] Unexpected error in health check loop: {e}")
                
                # Log error summary every 5 minutes
                time_since_last_summary = (datetime.now() - last_error_summary_time).total_seconds()
                if time_since_last_summary >= 300:  # 5 minutes
                    logger.error(
                        f"[SCHEDULER] Error summary: {consecutive_errors} consecutive "
                        f"health checks with errors in the last 5 minutes"
                    )
                    last_error_summary_time = datetime.now()
            
            # Wait for next interval
            # Requirement: 1.1
            try:
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                logger.info("[SCHEDULER] Health check loop cancelled")
                break
        
        logger.info("[SCHEDULER] Periodic health check loop stopped")
