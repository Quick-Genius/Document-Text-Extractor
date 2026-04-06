from celery import Task
from app.workers.celery_app import celery_app
from app.workers.processors.pdf_processor import PDFProcessor
from app.workers.processors.docx_processor import DOCXProcessor
from app.workers.processors.image_processor import ImageProcessor
from app.workers.processors.text_processor import TextProcessor
from app.core.config import settings

import requests
import tempfile
import os
from urllib.parse import urlparse
import logging
import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prisma import Prisma

# Lazy import Prisma to avoid initialization errors
def get_prisma() -> 'Prisma':
    from app.utils.db_pool import get_prisma_with_pool
    return get_prisma_with_pool()


def download_remote_file(source_url: str) -> str:
    """Download remote S3/http URL to a local temp file for processing."""
    import boto3
    
    parsed = urlparse(source_url)
    
    # Check if it's an S3 URL
    if "s3.amazonaws.com" in source_url or "s3." in parsed.netloc:
        # Extract bucket and key from S3 URL
        if ".s3." in parsed.netloc:
            bucket = parsed.netloc.split(".s3.")[0]
            key = parsed.path.lstrip("/")
        else:
            parts = parsed.path.lstrip("/").split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        suffix = os.path.splitext(key)[1] or ".pdf"
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        
        try:
            s3_client.download_file(bucket, key, temp_path)
            return temp_path
        except Exception as e:
            logger.error(f"Failed to download from S3: {e}")
            raise
    
    # Handle regular HTTP/HTTPS URLs
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme for download: {parsed.scheme}")

    response = requests.get(source_url, stream=True, timeout=(15.0, 60.0))
    response.raise_for_status()

    suffix = os.path.splitext(parsed.path)[1] or ".pdf"
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    with open(temp_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return temp_path


logger = logging.getLogger(__name__)

class CallbackTask(Task):
    """Base task with callbacks for lifecycle events"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Task {task_id} failed: {exc}")
        if args:
            asyncio.run(self.mark_job_failed(args[0], str(exc)))
        else:
            logger.error("Task on_failure called with empty args; cannot mark document failed by id")
    
    async def mark_job_failed(self, document_id: str, error: str):
        """Mark job as failed in database"""
        from app.utils.redis_client import create_task_redis
        from app.utils.db_pool import connect_prisma_with_timeout, disconnect_prisma_with_timeout

        db = get_prisma()
        task_redis = create_task_redis()

        # Connect to database with timeout protection
        await connect_prisma_with_timeout(db, timeout=30)
        
        try:
            document = await db.document.find_unique(
                where={"id": document_id},
                include={"job": True}
            )
            
            if document and document.job:
                await update_job_status(db, document.job.id, "FAILED", failed=True, error=error)
                await update_document_status(db, document_id, "FAILED")
                
                await task_redis.publish(
                    f"progress:{document.job.id}",
                    {
                        "type": "job_failed",
                        "jobId": document.job.id,
                        "error": error,
                        "timestamp": time.time()
                    }
                )
        finally:
            await disconnect_prisma_with_timeout(db, timeout=10)
            try:
                await asyncio.wait_for(task_redis.close(), timeout=5)
            except Exception:
                pass

@celery_app.task(
    bind=True, 
    base=CallbackTask, 
    name="app.workers.tasks.process_document_task",
    max_retries=0,
    acks_late=False,
    reject_on_worker_lost=True
)
def process_document_task(self, document_id: str, file_path: str):
    """
    Main document processing task
    
    Args:
        document_id: UUID of the document
        file_path: Path to the uploaded file
    """
    # Don't use asyncio.run() — it tries to gracefully cancel all pending
    # tasks left in the event loop by Prisma's query engine, which hangs
    # the Celery worker indefinitely. Instead, force-close the loop.
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            process_document_async(self, document_id, file_path)
        )
        return result
    finally:
        # Cancel any leftover tasks (Prisma background connections, etc.)
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # Give cancelled tasks a moment to finalize
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

async def process_document_async(task: Task, document_id: str, file_path: str):
    """
    Async document processing workflow with stage timeout tracking.
    
    Each task gets its own Prisma DB connection and its own Redis connection.
    This prevents the singleton-disconnect deadlock that occurs when multiple
    tasks share a single Redis connection across separate asyncio.run() calls.
    
    Uses distributed locking to coordinate concurrent task execution and prevent
    resource exhaustion during batch uploads.
    """
    from app.utils.redis_client import create_task_redis
    from app.utils.db_pool import connect_prisma_with_timeout, disconnect_prisma_with_timeout

    db = get_prisma()
    task_redis = create_task_redis()
    local_file_path = file_path
    temp_file_created = False
    job_id = None
    lock = None
    lock_acquired = False
    
    # Stage timeout limits (in seconds)
    STAGE_TIMEOUTS = {
        "parsing": 300,      # 5 minutes for parsing
        "extraction": 600,   # 10 minutes for extraction
        "storing": 60        # 1 minute for storing
    }

    # Connect to database with timeout protection
    await connect_prisma_with_timeout(db, timeout=settings.PRISMA_POOL_TIMEOUT)
    
    try:
        # Acquire distributed lock for task coordination
        # This limits concurrent task execution to prevent resource exhaustion
        lock_name = f"document:processing:lock"
        lock_timeout = settings.TASK_TOTAL_TIMEOUT  # Lock expires after task timeout
        
        # Try to acquire lock with retry logic
        max_lock_retries = 3
        lock_retry_delay = 2  # seconds
        
        for retry in range(max_lock_retries):
            try:
                # Create lock with timeout
                # Only BATCH_UPLOAD_MAX_CONCURRENT_TASKS can hold this lock simultaneously
                # For simplicity, we use a single lock with timeout
                lock = task_redis.redis.lock(
                    lock_name,
                    timeout=lock_timeout,
                    blocking_timeout=settings.PRISMA_POOL_TIMEOUT
                )
                
                lock_acquired = await lock.acquire()
                
                if lock_acquired:
                    logger.debug(f"Acquired distributed lock for document {document_id}")
                    break
                else:
                    if retry < max_lock_retries - 1:
                        logger.info(f"Failed to acquire lock, retrying in {lock_retry_delay}s (attempt {retry + 1}/{max_lock_retries})")
                        await asyncio.sleep(lock_retry_delay)
                        lock_retry_delay *= 2  # Exponential backoff
                    else:
                        logger.warning(f"Failed to acquire lock after {max_lock_retries} attempts, proceeding without lock")
            except Exception as e:
                logger.warning(f"Lock acquisition error: {e}, proceeding without lock")
                break
        
        # Get document and job
        document = await asyncio.wait_for(
            db.document.find_unique(
                where={"id": document_id},
                include={"job": True}
            ),
            timeout=settings.PRISMA_OPERATION_TIMEOUT
        )
        
        if not document or not document.job:
            raise Exception("Document or job not found")
        
        job_id = document.job.id
        
        # Track task start time for checkpoint validation
        task_start_time = time.time()
        
        def check_total_timeout():
            """Check if task has exceeded total timeout."""
            elapsed = time.time() - task_start_time
            if elapsed > settings.TASK_TOTAL_TIMEOUT:
                raise Exception(f"Task exceeded total timeout of {settings.TASK_TOTAL_TIMEOUT}s (elapsed: {elapsed:.0f}s)")
        
        # Check for cancellation
        if await check_cancellation(task_redis, job_id):
            logger.info(f"Job {job_id} was cancelled")
            await mark_job_cancelled(db, task_redis, job_id, document_id)
            return {"status": "cancelled"}
        
        # Stage 1: Job Started
        await publish_progress(db, task_redis, job_id, "job_started", "Starting document processing", 0)
        await update_job_status(db, job_id, "PROCESSING", started=True)
        await update_document_status(db, document_id, "PROCESSING")
        
        # Stage 2: Parsing Started
        await publish_progress(db, task_redis, job_id, "parsing_started", "Parsing document", 10)
        
        # Determine file type and select processor
        processor = get_processor_for_file(document.fileType)
        
        # Ensure local path for parsing (download from S3 URL if needed)
        if file_path.startswith("http"):
            local_file_path = download_remote_file(file_path)
            temp_file_created = True

        # Parse document with timeout
        parsing_start = time.time()
        try:
            parsed_data = await asyncio.wait_for(
                processor.parse(local_file_path),
                timeout=STAGE_TIMEOUTS["parsing"]
            )
            
            # Halt processing if extraction failed to return any reasonable text
            if not parsed_data.get("text") or len(parsed_data.get("text", "").strip()) < 10:
                raise ValueError("Document extraction failed: No readable text was recovered after engaging all fallback strategies.")
                
        except asyncio.TimeoutError:
            elapsed = time.time() - parsing_start
            error_msg = f"Parsing stage timed out after {elapsed:.0f} seconds (limit: {STAGE_TIMEOUTS['parsing']}s). Document may be too large or complex."
            logger.error(f"Document {document_id} parsing timeout: {error_msg}")
            await update_job_status(db, job_id, "FAILED", failed=True, error=error_msg)
            await update_document_status(db, document_id, "FAILED")
            await publish_progress(db, task_redis, job_id, "job_failed", error_msg, 0)
            raise Exception(error_msg)

        # Stage 3: Parsing Completed
        await publish_progress(db, task_redis, job_id, "parsing_completed", "Document parsed successfully", 40)
        
        # Checkpoint 1: After parsing, validate total timeout
        check_total_timeout()
        
        # Checkpoint 2: After parsing, before extraction
        if await check_cancellation(task_redis, job_id):
            await mark_job_cancelled(db, task_redis, job_id, document_id)
            return {"status": "cancelled"}
        
        # Stage 4: Extraction Started
        await publish_progress(db, task_redis, job_id, "extraction_started", "Extracting structured fields", 50)
        
        # Extract structured data with timeout
        extraction_start = time.time()
        try:
            extracted_data = await asyncio.wait_for(
                processor.extract_structured_data(parsed_data),
                timeout=STAGE_TIMEOUTS["extraction"]
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - extraction_start
            error_msg = f"Extraction stage timed out after {elapsed:.0f} seconds (limit: {STAGE_TIMEOUTS['extraction']}s). Document content may be too complex for AI processing."
            logger.error(f"Document {document_id} extraction timeout: {error_msg}")
            await update_job_status(db, job_id, "FAILED", failed=True, error=error_msg)
            await update_document_status(db, document_id, "FAILED")
            await publish_progress(db, task_redis, job_id, "job_failed", error_msg, 0)
            raise Exception(error_msg)
        
        # Stage 5: Extraction Completed
        await publish_progress(db, task_redis, job_id, "extraction_completed", "Extraction complete", 90)
        
        # Checkpoint 2: After extraction, validate total timeout
        check_total_timeout()
        
        # Checkpoint 3: After extraction, before storing
        if await check_cancellation(task_redis, job_id):
            await mark_job_cancelled(db, task_redis, job_id, document_id)
            return {"status": "cancelled"}
        
        # Stage 6: Store Results
        await publish_progress(db, task_redis, job_id, "storing_results", "Saving processed data", 95)
        
        # Checkpoint 3: Before storing, validate total timeout
        check_total_timeout()
        
        # Create ProcessedData record with timeout
        storing_start = time.time()
        try:
            from prisma import Json as PrismaJson
            
            metadata_value = extracted_data.get("metadata")
            if metadata_value and isinstance(metadata_value, dict):
                metadata = PrismaJson(metadata_value)
            else:
                metadata = None
            
            create_data = {
                "documentId": document_id,
                "extractedText": extracted_data.get("text") or "",
                "title": extracted_data.get("title"),
                "category": extracted_data.get("category"),
                "summary": extracted_data.get("summary"),
                "keywords": extracted_data.get("keywords") or [],
            }
            
            if metadata is not None:
                create_data["metadata"] = metadata
            
            processed_data = await asyncio.wait_for(
                db.processeddata.create(data=create_data),
                timeout=settings.PRISMA_OPERATION_TIMEOUT
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - storing_start
            error_msg = f"Database storage timed out after {elapsed:.0f} seconds (limit: {settings.PRISMA_OPERATION_TIMEOUT}s). Database may be overloaded."
            logger.error(f"Document {document_id} storing timeout: {error_msg}")
            await update_job_status(db, job_id, "FAILED", failed=True, error=error_msg)
            await update_document_status(db, document_id, "FAILED")
            await publish_progress(db, task_redis, job_id, "job_failed", error_msg, 0)
            raise Exception(error_msg)
        
        # Stage 7: Job Completed
        await publish_progress(db, task_redis, job_id, "job_completed", "Processing completed successfully", 100)
        await update_job_status(db, job_id, "COMPLETED", completed=True)
        await update_document_status(db, document_id, "COMPLETED")
        
        logger.info(f"Successfully processed document {document_id}")
        
        return {
            "status": "completed",
            "document_id": document_id,
            "processed_data_id": processed_data.id
        }
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
        if job_id:
            await publish_progress(db, task_redis, job_id, "job_failed", f"Processing failed: {str(e)}", 0)
        raise
        
    finally:
        # Release distributed lock if acquired
        if lock_acquired and lock:
            try:
                await asyncio.wait_for(lock.release(), timeout=5)
                logger.debug(f"Released distributed lock for document {document_id}")
            except Exception as e:
                logger.warning(f"Failed to release lock: {e}")
        
        try:
            # Clean up temporary file if one was downloaded
            if local_file_path != file_path and os.path.exists(local_file_path):
                os.remove(local_file_path)
        except Exception as cleanup_err:
            logger.warning(f"Failed to remove temp file {local_file_path}: {cleanup_err}")

        # Close task-scoped connections (NOT the global singleton!)
        # Use timeouts to prevent cleanup from blocking the worker
        from app.utils.db_pool import disconnect_prisma_with_timeout
        
        await disconnect_prisma_with_timeout(db, timeout=10)
        try:
            await asyncio.wait_for(task_redis.close(), timeout=5)
        except Exception as e:
            logger.warning(f"task_redis.close() failed/timed out: {e}")

def get_processor_for_file(file_type: str):
    """Select appropriate processor based on file type"""
    if "pdf" in file_type:
        return PDFProcessor()
    elif "wordprocessingml" in file_type or "msword" in file_type:
        return DOCXProcessor()
    elif "image" in file_type:
        return ImageProcessor()
    elif "text" in file_type:
        return TextProcessor()
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

async def check_cancellation(task_redis, job_id: str) -> bool:
    """Check if job has been cancelled"""
    cancel_flag = await task_redis.get(f"job:cancel:{job_id}")
    return cancel_flag is not None

async def mark_job_cancelled(db: 'Prisma', task_redis, job_id: str, document_id: str):
    """Mark job and document as cancelled"""
    await db.job.update(
        where={"id": job_id},
        data={"status": "CANCELLED"},
    )
    await db.document.update(
        where={"id": document_id},
        data={"status": "CANCELLED"},
    )
    await publish_progress(db, task_redis, job_id, "job_cancelled", "Job was cancelled by user", 0)

async def publish_progress(db: 'Prisma', task_redis, job_id: str, event_type: str, message: str, progress: int):
    """Publish progress event to Redis Pub/Sub with timeout protection"""
    from app.core.config import settings
    
    event = {
        "type": "progress",
        "jobId": job_id,
        "eventType": event_type,
        "message": message,
        "progress": progress,
        "timestamp": time.time()
    }
    
    # Publish to Pub/Sub channel
    await task_redis.publish(f"progress:{job_id}", event)
    
    # Also store in Redis hash for polling fallback
    await task_redis.hset(
        f"job:progress:{job_id}",
        mapping={
            "status": event_type,
            "message": message,
            "progress": str(progress),
            "updated_at": str(time.time())
        }
    )
    await task_redis.expire(f"job:progress:{job_id}", 3600)  # 1 hour TTL
    
    # Store in database with timeout protection
    try:
        await asyncio.wait_for(
            db.progressevent.create(
                data={
                    "jobId": job_id,
                    "eventType": event_type,
                    "message": message,
                    "progress": progress,
                }
            ),
            timeout=settings.PRISMA_OPERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning(f"Progress event creation timed out after {settings.PRISMA_OPERATION_TIMEOUT}s")
        # Don't fail the task if progress event creation times out
        pass

async def update_job_status(db: 'Prisma', job_id: str, status: str, started: bool = False, completed: bool = False, failed: bool = False, error: str = None):
    """
    Update job status in database with row-level locking.
    
    Uses SELECT FOR UPDATE to ensure atomic read-modify-write operations
    and prevent lost updates when multiple workers update the same job concurrently.
    """
    from app.core.config import settings
    
    update_data = {"status": status}
    
    if started:
        update_data["startedAt"] = datetime.now()
    if completed:
        update_data["completedAt"] = datetime.now()
    if failed:
        update_data["failedAt"] = datetime.now()
        update_data["errorMessage"] = error
    
    # Wrap update in transaction with row-level locking
    # This ensures atomic read-modify-write and prevents lost updates
    try:
        async with db.tx() as transaction:
            # Acquire row-level lock using SELECT FOR UPDATE
            # This prevents other transactions from modifying this job until we commit
            locked_job = await transaction.query_first(
                f"SELECT * FROM \"Job\" WHERE id = $1 FOR UPDATE",
                job_id
            )
            
            if not locked_job:
                logger.warning(f"Job {job_id} not found for status update")
                return
            
            # Perform the update within the locked transaction
            await transaction.job.update(
                where={"id": job_id},
                data=update_data,
            )
    except Exception as e:
        logger.error(f"Failed to update job status with locking: {e}")
        # Fallback to non-locked update if transaction fails
        try:
            await asyncio.wait_for(
                db.job.update(
                    where={"id": job_id},
                    data=update_data,
                ),
                timeout=settings.PRISMA_OPERATION_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Job status update timed out after {settings.PRISMA_OPERATION_TIMEOUT}s")
            raise Exception(f"Database operation timeout: job status update")

async def update_document_status(db: 'Prisma', document_id: str, status: str):
    """
    Update document status in database with timeout protection.
    """
    from app.core.config import settings
    
    try:
        await asyncio.wait_for(
            db.document.update(
                where={"id": document_id},
                data={"status": status},
            ),
            timeout=settings.PRISMA_OPERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"Document status update timed out after {settings.PRISMA_OPERATION_TIMEOUT}s")
        raise Exception(f"Database operation timeout: document status update")
