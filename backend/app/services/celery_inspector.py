"""
Celery Inspector Wrapper Module

Thin wrapper around Celery's inspect API used to determine which tasks are
currently being executed by workers, so the stuck-document recovery sweep
can tell a slow-but-alive task apart from one whose worker died.
"""

from typing import Dict, Any, List
from celery import Celery
from celery.app.control import Inspect
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)


class CeleryInspector:
    """Wrapper class for querying which tasks Celery workers are running."""

    def __init__(self, celery_app: Celery, timeout: int = 5):
        self.celery_app = celery_app
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=1)
        logger.debug(f"CeleryInspector initialized with timeout={timeout}s")

    def _get_inspector(self) -> Inspect:
        return self.celery_app.control.inspect()

    async def get_active_tasks(self) -> List[Dict[str, Any]]:
        """
        Get list of currently executing tasks from all workers.

        Returns an empty list if no workers are available, workers don't
        respond within the timeout, or an error occurs.
        """
        try:
            loop = asyncio.get_event_loop()
            inspector = self._get_inspector()

            active_tasks_dict = await asyncio.wait_for(
                loop.run_in_executor(self._executor, inspector.active),
                timeout=self.timeout
            )

            if not active_tasks_dict:
                logger.debug("No active tasks found (workers may be unavailable)")
                return []

            all_tasks = []
            for worker_name, tasks in active_tasks_dict.items():
                for task in tasks:
                    all_tasks.append({
                        'id': task.get('id'),
                        'name': task.get('name'),
                        'worker_pid': task.get('worker_pid'),
                        'args': task.get('args', []),
                        'kwargs': task.get('kwargs', {})
                    })

            logger.debug(f"Retrieved {len(all_tasks)} active tasks from Celery workers")
            return all_tasks

        except (asyncio.TimeoutError, FuturesTimeoutError):
            logger.warning(f"Celery inspector timeout after {self.timeout}s - workers may be unavailable")
            return []
        except Exception as e:
            logger.error(f"Failed to get active tasks from Celery: {e}", exc_info=True)
            return []

    def shutdown(self):
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=False)
        logger.debug("CeleryInspector executor shutdown")
