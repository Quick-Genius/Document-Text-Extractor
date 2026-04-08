"""
Celery Inspector Wrapper Module

This module provides a wrapper around Celery's inspect API to query worker state
and active task information. It includes timeout handling and error handling for
scenarios where workers are unavailable.

Requirements: 1.5, 6.1, 6.2
"""

from typing import Dict, Any, List, Optional
from celery import Celery
from celery.app.control import Inspect
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)


class CeleryInspector:
    """
    Wrapper class for querying Celery worker state.
    
    Provides methods to retrieve active tasks, task counts, and worker statistics
    with built-in timeout handling and error recovery.
    """
    
    def __init__(self, celery_app: Celery, timeout: int = 5):
        """
        Initialize the Celery inspector.
        
        Args:
            celery_app: The Celery application instance
            timeout: Timeout in seconds for inspector calls (default: 5)
        """
        self.celery_app = celery_app
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=1)
        logger.debug(f"CeleryInspector initialized with timeout={timeout}s")
    
    def _get_inspector(self) -> Inspect:
        """
        Get a Celery inspector instance.
        
        Returns:
            Celery Inspect instance
        """
        return self.celery_app.control.inspect()
    
    async def get_active_tasks(self) -> List[Dict[str, Any]]:
        """
        Get list of currently executing tasks from all workers.
        
        This method queries all Celery workers and returns information about
        tasks that are currently being executed. It includes timeout handling
        to prevent blocking if workers are unavailable.
        
        Returns:
            List of task info dicts with keys:
                - id: Task ID (celery task ID)
                - name: Task name (e.g., 'app.workers.tasks.process_document_task')
                - worker_pid: Worker process ID
                - args: Task arguments
                - kwargs: Task keyword arguments
            
            Returns empty list if:
                - No workers are available
                - Workers don't respond within timeout
                - An error occurs during query
        
        Requirements: 6.1 - Query Celery worker state to determine active task count
        """
        try:
            # Run inspector call in thread pool to enable timeout
            loop = asyncio.get_event_loop()
            inspector = self._get_inspector()
            
            # Execute the blocking inspect call with timeout
            active_tasks_dict = await asyncio.wait_for(
                loop.run_in_executor(self._executor, inspector.active),
                timeout=self.timeout
            )
            
            if not active_tasks_dict:
                logger.debug("No active tasks found (workers may be unavailable)")
                return []
            
            # Flatten the dict of {worker_name: [tasks]} into a single list
            all_tasks = []
            for worker_name, tasks in active_tasks_dict.items():
                for task in tasks:
                    task_info = {
                        'id': task.get('id'),
                        'name': task.get('name'),
                        'worker_pid': task.get('worker_pid'),
                        'args': task.get('args', []),
                        'kwargs': task.get('kwargs', {})
                    }
                    all_tasks.append(task_info)
            
            logger.debug(f"Retrieved {len(all_tasks)} active tasks from Celery workers")
            return all_tasks
            
        except asyncio.TimeoutError:
            logger.warning(f"Celery inspector timeout after {self.timeout}s - workers may be unavailable")
            return []
        except FuturesTimeoutError:
            logger.warning(f"Celery inspector timeout after {self.timeout}s - workers may be unavailable")
            return []
        except Exception as e:
            logger.error(f"Failed to get active tasks from Celery: {e}", exc_info=True)
            return []
    
    async def get_active_task_count(self) -> int:
        """
        Get count of currently executing tasks.
        
        This is a convenience method that returns just the count of active tasks
        without the full task details.
        
        Returns:
            Number of currently executing tasks (0 if workers unavailable)
        
        Requirements: 6.1 - Query Celery worker state to determine active task count
        """
        active_tasks = await self.get_active_tasks()
        count = len(active_tasks)
        logger.debug(f"Active task count: {count}")
        return count
    
    async def get_worker_stats(self) -> Dict[str, Any]:
        """
        Get worker statistics for monitoring.
        
        Retrieves comprehensive statistics about all Celery workers including:
        - Worker names and status
        - Pool configuration (concurrency, max-concurrency)
        - Task counts (active, reserved, total)
        - Broker connection status
        
        Returns:
            Dict with worker statistics:
                - workers: Dict of {worker_name: stats}
                - total_workers: Total number of workers
                - total_active_tasks: Total active tasks across all workers
                - available: Whether any workers are available
            
            Returns minimal dict if workers are unavailable:
                - workers: {}
                - total_workers: 0
                - total_active_tasks: 0
                - available: False
        
        Requirements: 6.2 - Add get_worker_stats() method for monitoring
        """
        try:
            loop = asyncio.get_event_loop()
            inspector = self._get_inspector()
            
            # Get stats with timeout
            stats_dict = await asyncio.wait_for(
                loop.run_in_executor(self._executor, inspector.stats),
                timeout=self.timeout
            )
            
            if not stats_dict:
                logger.warning("No worker stats available - workers may be unavailable")
                return {
                    'workers': {},
                    'total_workers': 0,
                    'total_active_tasks': 0,
                    'available': False
                }
            
            # Get active tasks for accurate count
            active_tasks_dict = await asyncio.wait_for(
                loop.run_in_executor(self._executor, inspector.active),
                timeout=self.timeout
            )
            
            # Calculate total active tasks
            total_active = 0
            if active_tasks_dict:
                for tasks in active_tasks_dict.values():
                    total_active += len(tasks)
            
            result = {
                'workers': stats_dict,
                'total_workers': len(stats_dict),
                'total_active_tasks': total_active,
                'available': True
            }
            
            logger.debug(f"Worker stats: {result['total_workers']} workers, {total_active} active tasks")
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Celery inspector timeout after {self.timeout}s - workers may be unavailable")
            return {
                'workers': {},
                'total_workers': 0,
                'total_active_tasks': 0,
                'available': False
            }
        except FuturesTimeoutError:
            logger.warning(f"Celery inspector timeout after {self.timeout}s - workers may be unavailable")
            return {
                'workers': {},
                'total_workers': 0,
                'total_active_tasks': 0,
                'available': False
            }
        except Exception as e:
            logger.error(f"Failed to get worker stats from Celery: {e}", exc_info=True)
            return {
                'workers': {},
                'total_workers': 0,
                'total_active_tasks': 0,
                'available': False
            }
    
    def shutdown(self):
        """
        Shutdown the thread pool executor.
        
        Should be called when the inspector is no longer needed to clean up resources.
        """
        self._executor.shutdown(wait=False)
        logger.debug("CeleryInspector executor shutdown")
