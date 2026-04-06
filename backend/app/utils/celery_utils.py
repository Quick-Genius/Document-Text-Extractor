"""
Celery utility functions for task management and queue cleanup
"""
import logging
from typing import List, Dict, Any
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def revoke_task(task_id: str, terminate: bool = True) -> bool:
    """
    Revoke a Celery task by ID
    
    Args:
        task_id: Celery task ID
        terminate: If True, terminate running tasks (SIGKILL)
    
    Returns:
        True if revocation was successful
    """
    try:
        celery_app.control.revoke(
            task_id,
            terminate=terminate,
            signal='SIGKILL' if terminate else 'SIGTERM'
        )
        logger.info(f"Revoked task {task_id} (terminate={terminate})")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke task {task_id}: {e}")
        return False


def purge_queue(queue_name: str = 'celery') -> int:
    """
    Purge all tasks from a specific queue
    
    Args:
        queue_name: Name of the queue to purge
    
    Returns:
        Number of tasks purged
    """
    try:
        count = celery_app.control.purge()
        logger.info(f"Purged {count} tasks from queue '{queue_name}'")
        return count
    except Exception as e:
        logger.error(f"Failed to purge queue '{queue_name}': {e}")
        return 0


def get_active_tasks() -> List[Dict[str, Any]]:
    """
    Get list of currently active (running) tasks
    
    Returns:
        List of active task dictionaries
    """
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        
        if not active:
            return []
        
        # Flatten the dict of workers to a list of tasks
        all_tasks = []
        for worker, tasks in active.items():
            for task in tasks:
                task['worker'] = worker
                all_tasks.append(task)
        
        return all_tasks
    except Exception as e:
        logger.error(f"Failed to get active tasks: {e}")
        return []


def get_reserved_tasks() -> List[Dict[str, Any]]:
    """
    Get list of reserved (queued but not yet running) tasks
    
    Returns:
        List of reserved task dictionaries
    """
    try:
        inspect = celery_app.control.inspect()
        reserved = inspect.reserved()
        
        if not reserved:
            return []
        
        # Flatten the dict of workers to a list of tasks
        all_tasks = []
        for worker, tasks in reserved.items():
            for task in tasks:
                task['worker'] = worker
                all_tasks.append(task)
        
        return all_tasks
    except Exception as e:
        logger.error(f"Failed to get reserved tasks: {e}")
        return []


def get_all_pending_tasks() -> List[Dict[str, Any]]:
    """
    Get all pending tasks (active + reserved)
    
    Returns:
        List of all pending task dictionaries
    """
    active = get_active_tasks()
    reserved = get_reserved_tasks()
    return active + reserved


def revoke_tasks_by_document_id(document_id: str) -> int:
    """
    Revoke all tasks associated with a specific document ID
    
    Args:
        document_id: Document ID to search for
    
    Returns:
        Number of tasks revoked
    """
    count = 0
    pending_tasks = get_all_pending_tasks()
    
    for task in pending_tasks:
        # Check if task args contain the document_id
        args = task.get('args', [])
        kwargs = task.get('kwargs', {})
        
        if document_id in args or kwargs.get('document_id') == document_id:
            task_id = task.get('id')
            if task_id and revoke_task(task_id):
                count += 1
    
    logger.info(f"Revoked {count} tasks for document {document_id}")
    return count


async def cleanup_stale_tasks(db) -> Dict[str, int]:
    """
    Clean up stale tasks that are in Celery queue but not in database
    
    Args:
        db: Prisma database client
    
    Returns:
        Dictionary with cleanup statistics
    """
    stats = {
        'checked': 0,
        'revoked': 0,
        'errors': 0
    }
    
    try:
        # Get all pending tasks from Celery
        pending_tasks = get_all_pending_tasks()
        stats['checked'] = len(pending_tasks)
        
        for task in pending_tasks:
            task_id = task.get('id')
            if not task_id:
                continue
            
            try:
                # Check if this task exists in database
                job = await db.job.find_first(
                    where={'celeryTaskId': task_id}
                )
                
                if not job:
                    # Task not in database - revoke it
                    logger.warning(f"Found stale task {task_id} not in database, revoking...")
                    if revoke_task(task_id):
                        stats['revoked'] += 1
                elif job.status in ['CANCELLED', 'COMPLETED', 'FAILED']:
                    # Task in database but already finished - revoke it
                    logger.warning(f"Found task {task_id} with status {job.status}, revoking...")
                    if revoke_task(task_id):
                        stats['revoked'] += 1
            except Exception as e:
                logger.error(f"Error checking task {task_id}: {e}")
                stats['errors'] += 1
        
        logger.info(f"Cleanup complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to cleanup stale tasks: {e}")
        stats['errors'] += 1
        return stats
