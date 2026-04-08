from fastapi import APIRouter, HTTPException
from app.workers.celery_app import celery_app
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health/rabbitmq")
async def check_rabbitmq_health():
    """
    Check RabbitMQ broker connectivity and return status information.
    
    Returns broker status, active workers count, and queue information.
    Returns 503 status code if connection fails.
    
    **Validates: Requirements 7.3, 7.4**
    """
    try:
        # Use Celery inspect API to check broker connectivity
        inspect = celery_app.control.inspect()
        
        # Get active queues from all workers
        active_queues = inspect.active_queues()
        
        # If active_queues is None, it means no workers are connected or broker is down
        if active_queues is None:
            logger.error("Cannot connect to RabbitMQ broker - no response from workers")
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to RabbitMQ broker"
            )
        
        # Get stats about workers
        stats = inspect.stats()
        active_workers = list(active_queues.keys()) if active_queues else []
        
        # Extract queue names from all workers
        queue_names = set()
        for worker_queues in active_queues.values():
            for queue_info in worker_queues:
                queue_names.add(queue_info.get('name', 'unknown'))
        
        logger.info(f"RabbitMQ health check successful: {len(active_workers)} workers, {len(queue_names)} queues")
        
        return {
            "status": "healthy",
            "broker": "rabbitmq",
            "active_workers": len(active_workers),
            "workers": active_workers,
            "queues": list(queue_names),
            "worker_stats": stats
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"RabbitMQ health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"RabbitMQ health check failed: {str(e)}"
        )
