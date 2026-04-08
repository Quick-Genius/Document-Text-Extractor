# Design Document: RabbitMQ Broker Migration

## Overview

This design specifies the migration of the document processing system's Celery task queue from Redis to RabbitMQ as the message broker. The migration addresses reliability concerns by leveraging RabbitMQ's superior message durability, persistence guarantees, and task acknowledgment mechanisms. Redis will be retained for its current roles: storing Celery task results (result backend) and managing WebSocket pub/sub for real-time progress updates.

### Goals

1. Replace Redis with RabbitMQ as the Celery message broker
2. Maintain Redis for result backend and WebSocket pub/sub functionality
3. Enable message persistence to survive broker restarts
4. Implement reliable task acknowledgment and requeuing
5. Preserve all existing task definitions and behavior
6. Maintain or improve system performance and throughput

### Non-Goals

1. Migrating the result backend from Redis to another system
2. Changing task serialization formats or task signatures
3. Modifying WebSocket pub/sub implementation
4. Implementing custom message routing beyond Celery defaults
5. Building a custom message broker abstraction layer

## Architecture

### System Components

```mermaid
graph TB
    subgraph "Application Layer"
        API[FastAPI Application]
        WS[WebSocket Manager]
    end
    
    subgraph "Task Queue Layer"
        CELERY[Celery App]
        WORKER[Celery Workers]
    end
    
    subgraph "Message Infrastructure"
        RMQ[RabbitMQ Broker<br/>Port 5672 AMQP<br/>Port 15672 Management]
        REDIS[Redis<br/>Result Backend<br/>WebSocket Pub/Sub]
    end
    
    subgraph "Storage Layer"
        DB[(PostgreSQL<br/>Database)]
        S3[S3 Storage]
    end
    
    API -->|Enqueue Tasks| CELERY
    CELERY -->|Send Messages| RMQ
    RMQ -->|Deliver Tasks| WORKER
    WORKER -->|Store Results| REDIS
    WORKER -->|Publish Progress| REDIS
    REDIS -->|Subscribe| WS
    WS -->|Real-time Updates| API
    WORKER -->|Update Status| DB
    WORKER -->|Read/Write Files| S3
    
    style RMQ fill:#ff9999
    style REDIS fill:#99ccff
```

### Message Flow


1. **Task Enqueue**: FastAPI application calls `task.apply_async()` to enqueue a document processing task
2. **Broker Send**: Celery serializes the task message (JSON) and sends it to RabbitMQ via AMQP
3. **Queue Storage**: RabbitMQ stores the message in a durable queue with disk persistence
4. **Task Delivery**: RabbitMQ delivers the task to an available Celery worker
5. **Task Execution**: Worker processes the document (parse, extract, store)
6. **Progress Updates**: Worker publishes progress events to Redis pub/sub
7. **Result Storage**: Worker stores task result in Redis result backend
8. **Task Acknowledgment**: Worker acknowledges task completion to RabbitMQ
9. **Queue Cleanup**: RabbitMQ removes the acknowledged message from the queue

### Connection Architecture

The system maintains two separate connection pools:

1. **RabbitMQ Connection Pool** (Celery Broker)
   - Protocol: AMQP 0-9-1
   - Pool size: 2-10 connections
   - Used for: Task enqueuing and delivery
   - Reconnection: Automatic with exponential backoff

2. **Redis Connection Pool** (Result Backend + Pub/Sub)
   - Protocol: Redis Protocol (RESP)
   - Pool size: Configured by Redis client
   - Used for: Task results, progress events, WebSocket pub/sub
   - Reconnection: Handled by Redis client library

## Components and Interfaces

### 1. Configuration Module (`app/core/config.py`)

**Changes Required:**

Add RabbitMQ configuration fields to the `Settings` class:

```python
# RabbitMQ Configuration
RABBITMQ_URL: Optional[str] = None
RABBITMQ_HOST: str = "localhost"
RABBITMQ_PORT: int = 5672
RABBITMQ_USER: str = "guest"
RABBITMQ_PASSWORD: str = "guest"
RABBITMQ_VHOST: str = "/"

@model_validator(mode='after')
def assemble_worker_urls(self) -> 'Settings':
    # Construct RabbitMQ URL if not provided
    if not self.RABBITMQ_URL:
        self.RABBITMQ_URL = (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"
        )
    
    # Use RabbitMQ for broker, Redis for result backend
    self.CELERY_BROKER_URL = self.RABBITMQ_URL
    
    # Construct Redis URL for result backend
    redis_base_url = self.REDIS_URL
    if not redis_base_url:
        if self.REDIS_PASSWORD:
            redis_base_url = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            redis_base_url = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    self.CELERY_RESULT_BACKEND = redis_base_url
    
    return self
```

**Interface:**
- Input: Environment variables (`RABBITMQ_URL`, `RABBITMQ_HOST`, etc.)
- Output: `settings.CELERY_BROKER_URL` (RabbitMQ AMQP URL)
- Output: `settings.CELERY_RESULT_BACKEND` (Redis URL)

### 2. Celery Application (`app/workers/celery_app.py`)

**Changes Required:**

Update Celery configuration to optimize for RabbitMQ:

```python
celery_app.conf.update(
    # Existing configuration
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.TASK_TIMEOUT,
    task_soft_time_limit=settings.TASK_TIMEOUT - 60,
    worker_concurrency=4,
    worker_max_tasks_per_child=100,
    
    # RabbitMQ-specific configuration
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Requeue on worker crash
    broker_connection_retry_on_startup=True,  # Retry on startup
    broker_connection_retry=True,  # Retry on connection loss
    broker_connection_max_retries=5,  # Max retry attempts
    
    # Connection pool settings
    broker_pool_limit=10,  # Max connections in pool
    broker_heartbeat=30,  # Heartbeat interval (seconds)
    broker_connection_timeout=30,  # Connection timeout (seconds)
    
    # Prefetch settings
    worker_prefetch_multiplier=1,  # Fetch 1 task at a time
    
    # Result backend (Redis)
    result_backend=settings.CELERY_RESULT_BACKEND,
    result_expires=3600,  # Results expire after 1 hour
)
```

**Interface:**
- Input: `settings.CELERY_BROKER_URL` (RabbitMQ)
- Input: `settings.CELERY_RESULT_BACKEND` (Redis)
- Output: Configured `celery_app` instance

### 3. Task Definitions (`app/workers/tasks.py`)

**Changes Required:**

Update task decorator to ensure compatibility with RabbitMQ:

```python
@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="app.workers.tasks.process_document_task",
    max_retries=0,  # Disable Celery's built-in retry (use requeuing)
    acks_late=True,  # Acknowledge after completion
    reject_on_worker_lost=True,  # Requeue on worker crash
    autoretry_for=(Exception,),  # Auto-retry on exceptions (optional)
    retry_backoff=True,  # Exponential backoff for retries
    retry_jitter=True,  # Add jitter to retry delays
)
def process_document_task(self, document_id: str, file_path: str):
    # Existing implementation remains unchanged
    ...
```

**Interface:**
- Input: Task parameters (`document_id`, `file_path`)
- Output: Task result (stored in Redis)
- Side Effects: RabbitMQ message acknowledgment

### 4. Health Check Endpoint

**New Component:**

Add a health check endpoint to verify RabbitMQ connectivity:

```python
# app/api/v1/health.py

from fastapi import APIRouter, HTTPException
from app.workers.celery_app import celery_app
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health/rabbitmq")
async def check_rabbitmq_health():
    """Check RabbitMQ broker connectivity"""
    try:
        # Inspect active queues
        inspect = celery_app.control.inspect()
        active_queues = inspect.active_queues()
        
        if active_queues is None:
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to RabbitMQ broker"
            )
        
        return {
            "status": "healthy",
            "broker": "rabbitmq",
            "active_workers": len(active_queues),
            "queues": list(active_queues.keys()) if active_queues else []
        }
    except Exception as e:
        logger.error(f"RabbitMQ health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"RabbitMQ health check failed: {str(e)}"
        )
```

**Interface:**
- Input: HTTP GET request to `/api/v1/health/rabbitmq`
- Output: JSON response with broker status
- Error: 503 Service Unavailable if RabbitMQ is down

### 5. Docker Compose Configuration

**Changes Required:**

Add RabbitMQ service to `docker-compose.yml`:

```yaml
services:
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    container_name: docproc-rabbitmq
    ports:
      - "5672:5672"    # AMQP protocol
      - "15672:15672"  # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-guest}
      RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST:-/}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - docproc-network

  # Update worker service to depend on RabbitMQ
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
    env_file:
      - ./backend/.env
    volumes:
      - ./backend:/app
      - storage_data:/app/storage
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - docproc-network

volumes:
  rabbitmq_data:
```

**Interface:**
- Input: Docker Compose configuration
- Output: Running RabbitMQ container with management UI
- Ports: 5672 (AMQP), 15672 (Management UI)

## Data Models

### RabbitMQ Queue Configuration

**Queue Name:** `celery` (default Celery queue)

**Queue Properties:**
- `durable`: `true` - Queue survives broker restarts
- `auto_delete`: `false` - Queue persists when no consumers
- `exclusive`: `false` - Queue can be accessed by multiple connections

**Message Properties:**
- `delivery_mode`: `2` - Persistent messages (written to disk)
- `content_type`: `application/json`
- `content_encoding`: `utf-8`

### Task Message Format

Celery task messages remain unchanged (JSON serialization):

```json
{
  "task": "app.workers.tasks.process_document_task",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "args": ["doc-id-123", "/path/to/file.pdf"],
  "kwargs": {},
  "retries": 0,
  "eta": null,
  "expires": null
}
```

### Result Backend Format (Redis)

Task results stored in Redis remain unchanged:

```
Key: celery-task-meta-<task_id>
Value: {
  "status": "SUCCESS",
  "result": {
    "status": "completed",
    "document_id": "doc-id-123",
    "processed_data_id": "processed-id-456"
  },
  "traceback": null,
  "children": [],
  "date_done": "2024-01-15T10:30:00.000Z"
}
```

## Error Handling

### Connection Failures

**Scenario:** RabbitMQ broker is unavailable during task enqueue

**Handling:**
1. Celery attempts to connect with exponential backoff
2. Retry up to 5 times with delays: 1s, 2s, 4s, 8s, 16s
3. If all retries fail, raise `OperationalError` to caller
4. Log error with context: `"Failed to connect to RabbitMQ after 5 attempts"`

**Code:**
```python
from celery.exceptions import OperationalError

try:
    task.apply_async(args=[document_id, file_path])
except OperationalError as e:
    logger.error(f"Failed to enqueue task: {e}")
    raise HTTPException(
        status_code=503,
        detail="Task queue is temporarily unavailable"
    )
```

### Worker Crashes

**Scenario:** Worker process crashes during task execution

**Handling:**
1. Task is not acknowledged to RabbitMQ (acks_late=True)
2. RabbitMQ detects worker disconnect via heartbeat timeout
3. RabbitMQ automatically requeues the unacknowledged task
4. Another worker picks up the requeued task
5. Task executes again from the beginning

**Configuration:**
```python
task_acks_late=True  # Acknowledge only after completion
task_reject_on_worker_lost=True  # Requeue on worker crash
broker_heartbeat=30  # Detect disconnects within 30 seconds
```

### Broker Restarts

**Scenario:** RabbitMQ broker restarts while tasks are queued

**Handling:**
1. Durable queues and persistent messages survive restart
2. Workers automatically reconnect with exponential backoff
3. Queued tasks remain intact and are delivered after reconnection
4. In-flight tasks (not yet acknowledged) are requeued

**Configuration:**
```python
# Queue durability
x-durable: true

# Message persistence
delivery_mode: 2

# Worker reconnection
broker_connection_retry=True
broker_connection_max_retries=0  # Infinite retries
```

### Task Failures

**Scenario:** Task fails with an exception during processing

**Handling:**
1. Worker catches exception in task code
2. Worker rejects the task message to RabbitMQ
3. Celery's retry logic handles the failure (if configured)
4. Task is marked as FAILED in result backend
5. Error details are stored in Redis and database

**Code:**
```python
try:
    result = process_document_async(document_id, file_path)
except Exception as e:
    logger.error(f"Task failed: {e}")
    # Task is rejected, Celery handles retry logic
    raise
```

### Message Acknowledgment Timeout

**Scenario:** Task takes longer than expected, RabbitMQ suspects worker is stuck

**Handling:**
1. RabbitMQ has a consumer timeout (default: 30 minutes)
2. If task exceeds timeout without acknowledgment, connection is closed
3. Task is automatically requeued
4. Configure timeout to match task time limit

**Configuration:**
```python
# Celery task timeout
task_time_limit=1800  # 30 minutes hard limit

# RabbitMQ consumer timeout (set in RabbitMQ config)
consumer_timeout=1800000  # 30 minutes in milliseconds
```

## Testing Strategy

This feature involves infrastructure configuration and integration between Celery, RabbitMQ, and Redis. Property-based testing is not applicable for infrastructure setup and external service integration. Instead, the testing strategy focuses on integration tests, smoke tests, and manual verification.

### Integration Tests

**Test 1: Task Enqueue and Execution**
- Enqueue a document processing task
- Verify task is delivered to worker
- Verify task executes successfully
- Verify result is stored in Redis
- Verify progress events are published

**Test 2: Message Persistence**
- Enqueue multiple tasks
- Stop RabbitMQ broker
- Restart RabbitMQ broker
- Verify all tasks are still in queue
- Verify tasks execute after restart

**Test 3: Worker Crash Recovery**
- Enqueue a task
- Simulate worker crash during execution (kill process)
- Verify task is requeued by RabbitMQ
- Verify task is picked up by another worker
- Verify task completes successfully

**Test 4: Connection Resilience**
- Start system with RabbitMQ down
- Verify Celery retries connection
- Start RabbitMQ
- Verify Celery connects successfully
- Enqueue and execute a task

**Test 5: Concurrent Task Processing**
- Enqueue 100 tasks simultaneously
- Verify all tasks are accepted by RabbitMQ
- Verify tasks are distributed across workers
- Verify all tasks complete successfully
- Measure throughput and latency

### Smoke Tests

**Test 1: RabbitMQ Service Availability**
- Verify RabbitMQ is running on port 5672
- Verify Management UI is accessible on port 15672
- Verify default credentials work

**Test 2: Celery Configuration**
- Verify `CELERY_BROKER_URL` points to RabbitMQ
- Verify `CELERY_RESULT_BACKEND` points to Redis
- Verify Celery app starts without errors

**Test 3: Health Check Endpoint**
- Call `/api/v1/health/rabbitmq`
- Verify response indicates healthy status
- Verify active workers are listed

### Manual Verification

**Test 1: Management UI Inspection**
- Access RabbitMQ Management UI at `http://localhost:15672`
- Verify `celery` queue exists and is durable
- Enqueue tasks and observe queue depth
- Verify message rates and consumer status

**Test 2: Performance Comparison**
- Measure task enqueue latency (Redis vs RabbitMQ)
- Measure task execution throughput (Redis vs RabbitMQ)
- Verify performance is maintained or improved

**Test 3: Log Inspection**
- Verify connection events are logged (connect, disconnect, reconnect)
- Verify task lifecycle events are logged (enqueue, start, complete)
- Verify error conditions are logged with context

### Test Environment Setup

**Docker Compose Test Environment:**
```bash
# Start all services
docker-compose up -d

# Verify RabbitMQ is healthy
docker-compose ps rabbitmq

# Access Management UI
open http://localhost:15672

# Run integration tests
cd backend
pytest tests/integration/test_rabbitmq_migration.py -v

# Monitor logs
docker-compose logs -f worker
```

**Local Development Setup:**
```bash
# Install RabbitMQ (macOS)
brew install rabbitmq
brew services start rabbitmq

# Install RabbitMQ (Ubuntu)
sudo apt-get install rabbitmq-server
sudo systemctl start rabbitmq-server

# Enable management plugin
sudo rabbitmq-plugins enable rabbitmq_management

# Access Management UI
open http://localhost:15672
```

## Deployment Considerations

### Environment Variables

**Required Variables:**
```bash
# RabbitMQ Configuration
RABBITMQ_URL=amqp://user:password@rabbitmq-host:5672/vhost
# OR individual components:
RABBITMQ_HOST=rabbitmq-host
RABBITMQ_PORT=5672
RABBITMQ_USER=celery_user
RABBITMQ_PASSWORD=secure_password
RABBITMQ_VHOST=/docproc

# Redis Configuration (for result backend)
REDIS_URL=redis://redis-host:6379/0
# OR individual components:
REDIS_HOST=redis-host
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=redis_password
```

### Production Deployment

**RabbitMQ Cluster Setup:**
- Deploy RabbitMQ in a cluster for high availability
- Use a load balancer for AMQP connections
- Configure queue mirroring for redundancy
- Set up monitoring and alerting

**Connection Pool Tuning:**
```python
# Production settings
broker_pool_limit=20  # Increase for high throughput
worker_concurrency=8  # Match CPU cores
worker_prefetch_multiplier=1  # Prevent task hoarding
```

**Resource Limits:**
- RabbitMQ memory: 2GB minimum, 4GB recommended
- RabbitMQ disk: 10GB minimum for message persistence
- Worker memory: 512MB per worker process
- Worker CPU: 1 core per 4 concurrent tasks

### Migration Steps

**Phase 1: Preparation**
1. Install RabbitMQ in development environment
2. Update configuration files with RabbitMQ settings
3. Run integration tests to verify functionality
4. Document rollback procedure

**Phase 2: Staging Deployment**
1. Deploy RabbitMQ to staging environment
2. Update application configuration to use RabbitMQ
3. Deploy updated application code
4. Run smoke tests and integration tests
5. Monitor for 24 hours

**Phase 3: Production Deployment**
1. Schedule maintenance window (low traffic period)
2. Deploy RabbitMQ to production
3. Update application configuration
4. Deploy updated application code
5. Restart workers to pick up new configuration
6. Monitor queue depth and task throughput
7. Verify no tasks are lost during transition

**Phase 4: Validation**
1. Process test documents through the system
2. Verify task persistence by restarting RabbitMQ
3. Verify worker crash recovery
4. Monitor performance metrics for 7 days
5. Document any issues and resolutions

### Rollback Procedure

If issues arise during migration:

1. **Immediate Rollback:**
   - Update `CELERY_BROKER_URL` back to Redis URL
   - Restart workers to reconnect to Redis
   - Verify tasks are processing normally

2. **Data Preservation:**
   - RabbitMQ queues can be drained before rollback
   - Export queued tasks using Management UI
   - Re-enqueue tasks to Redis if needed

3. **Configuration Rollback:**
   ```bash
   # Revert to Redis broker
   export CELERY_BROKER_URL=redis://localhost:6379/0
   
   # Restart workers
   docker-compose restart worker
   ```

### Monitoring and Alerting

**Key Metrics:**
- Queue depth (alert if > 1000 tasks)
- Message rate (tasks/second)
- Consumer count (alert if 0 workers)
- Connection failures (alert on repeated failures)
- Task latency (alert if > 5 seconds for idle queue)

**RabbitMQ Management UI:**
- Access at `http://rabbitmq-host:15672`
- Monitor queue depth and message rates
- View consumer status and connection details
- Export metrics for external monitoring

**Logging:**
```python
# Connection events
logger.info("Connected to RabbitMQ broker")
logger.warning("RabbitMQ connection lost, retrying...")
logger.error("Failed to connect to RabbitMQ after 5 attempts")

# Task events
logger.info(f"Task {task_id} enqueued to RabbitMQ")
logger.info(f"Task {task_id} acknowledged by worker")
logger.warning(f"Task {task_id} requeued due to worker crash")
```

## Documentation

### Migration Guide

A comprehensive migration guide will be created covering:
1. RabbitMQ installation (development and production)
2. Configuration changes required
3. Environment variable setup
4. Docker Compose updates
5. Testing procedures
6. Deployment steps
7. Rollback procedures
8. Troubleshooting common issues

### Developer Documentation

Updates to developer documentation:
1. Local development setup with RabbitMQ
2. Accessing RabbitMQ Management UI
3. Debugging task queue issues
4. Understanding message persistence and acknowledgment
5. Performance tuning guidelines

### Operations Documentation

New operations documentation:
1. RabbitMQ cluster setup and maintenance
2. Monitoring and alerting configuration
3. Backup and recovery procedures
4. Scaling workers and broker capacity
5. Security best practices (authentication, TLS)

## Security Considerations

### Authentication

- Use strong credentials for RabbitMQ (not default guest/guest)
- Store credentials in environment variables, not in code
- Use different credentials for development and production
- Rotate credentials periodically

### Network Security

- Restrict RabbitMQ port access to application servers only
- Use TLS for AMQP connections in production
- Enable TLS for Management UI in production
- Use firewall rules to limit access

### Authorization

- Create dedicated RabbitMQ user for Celery with minimal permissions
- Grant only necessary permissions: configure, write, read on specific vhost
- Use separate vhosts for different environments (dev, staging, prod)

### Example Production Configuration

```python
# Production RabbitMQ URL with TLS
RABBITMQ_URL = (
    "amqps://celery_user:secure_password@rabbitmq.example.com:5671/prod"
    "?ssl_cert_reqs=required"
    "&ssl_ca_certs=/path/to/ca_certificate.pem"
)
```

## Performance Optimization

### Connection Pooling

- Use connection pool to reduce connection overhead
- Configure pool size based on worker concurrency
- Monitor pool utilization and adjust as needed

```python
broker_pool_limit=10  # Max 10 connections in pool
```

### Prefetch Configuration

- Set prefetch multiplier to 1 to prevent task hoarding
- Ensures fair distribution across workers
- Prevents memory issues with large tasks

```python
worker_prefetch_multiplier=1
```

### Message Batching

- For high-throughput scenarios, consider batching small tasks
- Reduces per-message overhead
- Trade-off: increased latency for individual tasks

### Queue Optimization

- Use separate queues for different task priorities (future enhancement)
- Configure queue length limits to prevent memory exhaustion
- Monitor queue depth and scale workers accordingly

## Future Enhancements

### Priority Queues

Implement task prioritization using RabbitMQ priority queues:
- High priority: User-initiated single document processing
- Normal priority: Batch document processing
- Low priority: Background maintenance tasks

### Dead Letter Queues

Implement dead letter queues for failed tasks:
- Tasks that fail after max retries go to DLQ
- Manual inspection and reprocessing of failed tasks
- Prevents poison messages from blocking queue

### Task Routing

Implement advanced task routing:
- Route tasks to specific workers based on document type
- Route large documents to high-memory workers
- Route image processing to GPU-enabled workers

### Monitoring Integration

Integrate with monitoring platforms:
- Prometheus metrics exporter for RabbitMQ
- Grafana dashboards for queue visualization
- PagerDuty alerts for critical failures

## Conclusion

This design provides a comprehensive plan for migrating from Redis to RabbitMQ as the Celery message broker. The migration improves system reliability through message persistence, durable queues, and automatic task requeuing while maintaining Redis for fast result storage and WebSocket pub/sub. The design preserves all existing functionality and task definitions, ensuring a smooth transition with minimal code changes.

Key benefits of this migration:
1. **Reliability**: Durable queues and persistent messages survive broker restarts
2. **Fault Tolerance**: Automatic task requeuing on worker crashes
3. **Monitoring**: Built-in Management UI for queue inspection
4. **Scalability**: Better support for high-throughput scenarios
5. **Separation of Concerns**: Dedicated broker for task queuing, Redis for fast storage

The implementation follows Celery best practices and RabbitMQ recommendations, ensuring a production-ready solution that maintains or improves system performance.
