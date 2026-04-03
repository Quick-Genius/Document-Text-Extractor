from celery import Task
from app.workers.celery_app import celery_app
from app.workers.processors.pdf_processor import PDFProcessor
from app.workers.processors.docx_processor import DOCXProcessor
from app.workers.processors.image_processor import ImageProcessor
from app.workers.processors.text_processor import TextProcessor
from app.utils.redis_client import redis_client

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
    from prisma import Prisma
    return Prisma()


def download_remote_file(source_url: str) -> str:
    """Download remote S3/http URL to a local temp file for processing."""
    from app.core.config import settings
    import boto3
    
    parsed = urlparse(source_url)
    
    # Check if it's an S3 URL
    if "s3.amazonaws.com" in source_url or "s3." in parsed.netloc:
        # Extract bucket and key from S3 URL
        # Format: https://bucket.s3.region.amazonaws.com/key
        if ".s3." in parsed.netloc:
            bucket = parsed.netloc.split(".s3.")[0]
            key = parsed.path.lstrip("/")
        else:
            # Alternative format: https://s3.region.amazonaws.com/bucket/key
            parts = parsed.path.lstrip("/").split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        
        # Download from S3 using boto3
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

    response = requests.get(source_url, stream=True)
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
        db = get_prisma()
        await db.connect()
        
        try:
            # Get job
            document = await db.document.find_unique(
                where={"id": document_id},
                include={"job": True}
            )
            
            if document and document.job:
                # Update job status
                await update_job_status(db, document.job.id, "FAILED", failed=True, error=error)
                
                # Update document status
                await update_document_status(db, document_id, "FAILED")
                
                # Publish failure event
                await redis_client.publish(
                    f"progress:{document.job.id}",
                    {
                        "type": "job_failed",
                        "jobId": document.job.id,
                        "error": error,
                        "timestamp": time.time()
                    }
                )
        finally:
            await db.disconnect()

@celery_app.task(bind=True, base=CallbackTask, name="app.workers.tasks.process_document_task")
def process_document_task(self, document_id: str, file_path: str):
    """
    Main document processing task
    
    Args:
        document_id: UUID of the document
        file_path: Path to the uploaded file
    """
    return asyncio.run(process_document_async(self, document_id, file_path))

async def process_document_async(task: Task, document_id: str, file_path: str):
    """
    Async document processing workflow with stage timeout tracking
    """
    db = get_prisma()
    local_file_path = file_path
    temp_file_created = False
    job_id = None
    
    # Stage timeout limits (in seconds)
    STAGE_TIMEOUTS = {
        "parsing": 300,      # 5 minutes for parsing
        "extraction": 600,   # 10 minutes for extraction
        "storing": 60        # 1 minute for storing
    }

    # Prisma query engine spawns a subprocess with stdout/stderr from sys.stdout/sys.stderr.
    # In Celery worker context these can be LoggingProxy objects with no fileno().
    # Force native stdio to avoid subprocess startup error.
    import sys
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    try:
        if not hasattr(sys.stdout, "fileno"):
            sys.stdout = sys.__stdout__
        if not hasattr(sys.stderr, "fileno"):
            sys.stderr = sys.__stderr__

        await db.connect()
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
    
    try:
        # Get document and job
        document = await db.document.find_unique(
            where={"id": document_id},
            include={"job": True}
        )
        
        if not document or not document.job:
            raise Exception("Document or job not found")
        
        job_id = document.job.id
        
        # Check for cancellation
        if await check_cancellation(job_id):
            logger.info(f"Job {job_id} was cancelled")
            await mark_job_cancelled(db, job_id, document_id)
            return {"status": "cancelled"}
        
        # Stage 1: Job Started
        await publish_progress(db, job_id, "job_started", "Starting document processing", 0)
        await update_job_status(db, job_id, "PROCESSING", started=True)
        await update_document_status(db, document_id, "PROCESSING")
        
        # Stage 2: Parsing Started
        await publish_progress(db, job_id, "parsing_started", "Parsing document", 10)
        
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
        except asyncio.TimeoutError:
            elapsed = time.time() - parsing_start
            error_msg = f"Parsing stage timed out after {elapsed:.0f} seconds (limit: {STAGE_TIMEOUTS['parsing']}s). Document may be too large or complex."
            logger.error(f"Document {document_id} parsing timeout: {error_msg}")
            await update_job_status(db, job_id, "FAILED", failed=True, error=error_msg)
            await update_document_status(db, document_id, "FAILED")
            await publish_progress(db, job_id, "job_failed", error_msg, 0)
            raise Exception(error_msg)

        # Stage 3: Parsing Completed
        await publish_progress(db, job_id, "parsing_completed", "Document parsed successfully", 40)
        
        # Checkpoint 2: After parsing, before extraction
        if await check_cancellation(job_id):
            await mark_job_cancelled(db, job_id, document_id)
            return {"status": "cancelled"}
        
        # Stage 4: Extraction Started
        await publish_progress(db, job_id, "extraction_started", "Extracting structured fields", 50)
        
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
            await publish_progress(db, job_id, "job_failed", error_msg, 0)
            raise Exception(error_msg)
        
        # Stage 5: Extraction Completed
        await publish_progress(db, job_id, "extraction_completed", "Extraction complete", 90)
        
        # Checkpoint 3: After extraction, before storing
        if await check_cancellation(job_id):
            await mark_job_cancelled(db, job_id, document_id)
            return {"status": "cancelled"}
        
        # Stage 6: Store Results
        await publish_progress(db, job_id, "storing_results", "Saving processed data", 95)
        
        # Create ProcessedData record with timeout
        storing_start = time.time()
        try:
            # Prepare metadata - use Prisma.Json for JSON fields
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
            
            # Only add metadata if it's not None
            if metadata is not None:
                create_data["metadata"] = metadata
            
            processed_data = await asyncio.wait_for(
                db.processeddata.create(data=create_data),
                timeout=STAGE_TIMEOUTS["storing"]
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - storing_start
            error_msg = f"Database storage timed out after {elapsed:.0f} seconds (limit: {STAGE_TIMEOUTS['storing']}s). Database may be overloaded."
            logger.error(f"Document {document_id} storing timeout: {error_msg}")
            await update_job_status(db, job_id, "FAILED", failed=True, error=error_msg)
            await update_document_status(db, document_id, "FAILED")
            await publish_progress(db, job_id, "job_failed", error_msg, 0)
            raise Exception(error_msg)
        
        # Stage 7: Job Completed
        await publish_progress(db, job_id, "job_completed", "Processing completed successfully", 100)
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
            await publish_progress(db, job_id, "job_failed", f"Processing failed: {str(e)}", 0)
        raise
        
    finally:
        try:
            # Clean up temporary file if one was downloaded
            if local_file_path != file_path and os.path.exists(local_file_path):
                os.remove(local_file_path)
        except Exception as cleanup_err:
            logger.warning(f"Failed to remove temp file {local_file_path}: {cleanup_err}")

        await db.disconnect()

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

async def check_cancellation(job_id: str) -> bool:
    """Check if job has been cancelled"""
    cancel_flag = await redis_client.get(f"job:cancel:{job_id}")
    return cancel_flag is not None

async def mark_job_cancelled(db: 'Prisma', job_id: str, document_id: str):
    """Mark job and document as cancelled"""
    await db.job.update(
        where={"id": job_id},
        data={"status": "CANCELLED"},
    )
    await db.document.update(
        where={"id": document_id},
        data={"status": "CANCELLED"},
    )
    await publish_progress(db, job_id, "job_cancelled", "Job was cancelled by user", 0)

async def publish_progress(db: 'Prisma', job_id: str, event_type: str, message: str, progress: int):
    """Publish progress event to Redis Pub/Sub"""
    event = {
        "type": "progress",
        "jobId": job_id,
        "eventType": event_type,
        "message": message,
        "progress": progress,
        "timestamp": time.time()
    }
    
    # Publish to Pub/Sub channel
    await redis_client.publish(f"progress:{job_id}", event)
    
    # Also store in Redis hash for polling fallback
    await redis_client.hset(
        f"job:progress:{job_id}",
        mapping={
            "status": event_type,
            "message": message,
            "progress": str(progress),
            "updated_at": str(time.time())
        }
    )
    await redis_client.expire(f"job:progress:{job_id}", 3600)  # 1 hour TTL
    
    # Store in database
    await db.progressevent.create(
        data={
            "jobId": job_id,
            "eventType": event_type,
            "message": message,
            "progress": progress,
        }
    )

async def update_job_status(db: 'Prisma', job_id: str, status: str, started: bool = False, completed: bool = False, failed: bool = False, error: str = None):
    """Update job status in database"""
    update_data = {"status": status}
    
    if started:
        update_data["startedAt"] = datetime.now()
    if completed:
        update_data["completedAt"] = datetime.now()
    if failed:
        update_data["failedAt"] = datetime.now()
        update_data["errorMessage"] = error
    
    await db.job.update(
        where={"id": job_id},
        data=update_data,
    )

async def update_document_status(db: 'Prisma', document_id: str, status: str):
    """Update document status in database"""
    await db.document.update(
        where={"id": document_id},
        data={"status": status},
    )
