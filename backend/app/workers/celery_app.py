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
    
    # RabbitMQ-specific configuration
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Requeue on worker crash
    broker_connection_retry_on_startup=True,  # Retry on startup
    broker_connection_retry=True,  # Enable automatic reconnection
    broker_connection_max_retries=5,  # Max retry attempts for initial connection
    
    # Connection pool settings
    broker_pool_limit=10,  # Max connections in pool
    broker_heartbeat=30,  # Heartbeat interval (seconds)
    broker_connection_timeout=30,  # Connection timeout (seconds)
    
    # Result backend (Redis)
    result_backend=settings.CELERY_RESULT_BACKEND,
    result_expires=3600,  # Results expire after 1 hour
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

# Connection event handlers
from celery.signals import (
    worker_ready, 
    worker_shutdown, 
    beat_init,
    before_task_publish,
    task_prerun,
    task_postrun,
    task_retry,
    task_rejected
)

@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Log successful broker connection when worker starts"""
    logger.info("Celery worker connected to RabbitMQ broker successfully")

@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Log broker disconnection when worker shuts down"""
    logger.info("Celery worker disconnecting from RabbitMQ broker")

@beat_init.connect
def on_beat_init(sender, **kwargs):
    """Log when beat scheduler connects to broker"""
    logger.info("Celery beat scheduler connected to RabbitMQ broker")

# Task lifecycle event handlers
@before_task_publish.connect
def on_task_enqueue(sender=None, headers=None, body=None, **kwargs):
    """Log task enqueue events with task ID and name"""
    task_id = headers.get('id') if headers else None
    task_name = headers.get('task') if headers else sender
    logger.info(f"Task enqueued: {task_name} [ID: {task_id}]")

@task_prerun.connect
def on_task_start(sender=None, task_id=None, task=None, **kwargs):
    """Log when task starts execution (implicit acknowledgment from queue)"""
    task_name = task.name if task else sender
    logger.info(f"Task acknowledged and started: {task_name} [ID: {task_id}]")

@task_postrun.connect
def on_task_complete(sender=None, task_id=None, task=None, state=None, **kwargs):
    """Log when task completes successfully (will be acknowledged to broker)"""
    task_name = task.name if task else sender
    logger.info(f"Task completed successfully: {task_name} [ID: {task_id}]")

@task_retry.connect
def on_task_retry(sender=None, task_id=None, reason=None, **kwargs):
    """Log when task is retried"""
    task_name = sender.name if sender else "unknown"
    logger.info(f"Task retry scheduled: {task_name} [ID: {task_id}] - Reason: {reason}")

@task_rejected.connect
def on_task_rejected(sender=None, task_id=None, **kwargs):
    """Log when task is rejected and requeued due to worker crash or failure"""
    task_name = sender.name if sender else "unknown"
    logger.warning(f"Task rejected and requeued: {task_name} [ID: {task_id}] - Worker crash or connection loss")

# Configure Celery to log connection events
# Celery's internal connection handling will log:
# - INFO: Successful connections and reconnections (via kombu.connection)
# - WARNING: Connection loss and retry attempts (via kombu.connection)
# - ERROR: Connection failures after max retries (via celery.app.log)
# 
# The signal handlers above provide explicit logging for:
# - Worker startup connection (INFO)
# - Worker shutdown disconnection (INFO)
# - Beat scheduler connection (INFO)
#
# Task lifecycle event logging:
# - Task enqueue: Logged when task is sent to RabbitMQ (before_task_publish)
# - Task acknowledgment: Logged when worker picks up task from queue (task_prerun)
# - Task completion: Logged when task finishes successfully (task_postrun)
# - Task requeue: Logged when task is rejected due to worker crash (task_rejected)
#
# This satisfies Requirement 7.5: Log RabbitMQ connection events 
# (connect, disconnect, reconnect) at INFO level and task lifecycle events

# Log Celery configuration at startup
logger.info("=" * 60)
logger.info("Celery Worker Configuration:")
logger.info(f"  Concurrency: {celery_app.conf.worker_concurrency}")
logger.info(f"  Prefetch Multiplier: {celery_app.conf.worker_prefetch_multiplier}")
logger.info(f"  Task Time Limit: {celery_app.conf.task_time_limit}s")
logger.info(f"  Task Soft Time Limit: {celery_app.conf.task_soft_time_limit}s")
logger.info(f"  Max Tasks Per Child: {celery_app.conf.worker_max_tasks_per_child}")
logger.info(f"  Task Acks Late: {celery_app.conf.task_acks_late}")
logger.info(f"  Broker: {settings.CELERY_BROKER_URL.split('@')[-1] if '@' in settings.CELERY_BROKER_URL else settings.CELERY_BROKER_URL}")
logger.info("=" * 60)

# Validate configuration and log warnings if suboptimal
config_warnings = []

if celery_app.conf.worker_concurrency < 4:
    config_warnings.append(
        f"Worker concurrency is {celery_app.conf.worker_concurrency}, which is below the recommended minimum of 4. "
        "This may limit parallel processing capacity. Consider setting --concurrency=4 or higher in docker-compose.yml."
    )

if celery_app.conf.worker_prefetch_multiplier != 1:
    config_warnings.append(
        f"Worker prefetch multiplier is {celery_app.conf.worker_prefetch_multiplier}, which may cause task hoarding. "
        "The recommended value is 1 for fair task distribution across workers."
    )

if not celery_app.conf.task_acks_late:
    config_warnings.append(
        "Task acks_late is disabled. Tasks may be lost if worker crashes before completion. "
        "Enable task_acks_late=True for better reliability."
    )

if config_warnings:
    logger.warning("=" * 60)
    logger.warning("CELERY CONFIGURATION WARNINGS:")
    for i, warning in enumerate(config_warnings, 1):
        logger.warning(f"{i}. {warning}")
    logger.warning("=" * 60)
else:
    logger.info("Celery configuration is optimal for parallel processing")

logger.info("Celery app configured successfully")
