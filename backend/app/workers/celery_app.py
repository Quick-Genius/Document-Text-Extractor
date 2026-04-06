from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "document_processor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"]  # Enable task registration
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.TASK_TIMEOUT,
    task_soft_time_limit=settings.TASK_TIMEOUT - 60,
    worker_prefetch_multiplier=1,
    worker_concurrency=4,  # Allow 4 concurrent tasks
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

# Task routes
# celery_app.conf.task_routes = {
#     "app.workers.tasks.process_document_task": {"queue": "default"},
# }

# Celery events
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks if needed"""
    pass

logger.info("Celery app configured successfully")
