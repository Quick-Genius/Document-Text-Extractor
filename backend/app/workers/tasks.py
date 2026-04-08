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

logger = logging.getLogger(__name__)


def get_prisma() -> 'Prisma':
    from app.utils.db_pool import get_prisma_with_pool
    return get_prisma_with_pool()


def download_remote_file(source_url: str) -> str:
    """Download S3/HTTP URL to a local temp file."""
    import boto3
    parsed = urlparse(source_url)

    if "s3.amazonaws.com" in source_url or "s3." in parsed.netloc:
        if ".s3." in parsed.netloc:
            bucket = parsed.netloc.split(".s3.")[0]
            key = parsed.path.lstrip("/")
        else:
            parts = parsed.path.lstrip("/").split("/", 1)
            bucket, key = parts[0], (parts[1] if len(parts) > 1 else "")

        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        suffix = os.path.splitext(key)[1] or ".pdf"
        fd, tmp = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        s3.download_file(bucket, key, tmp)
        return tmp

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    resp = requests.get(source_url, stream=True, timeout=(15.0, 60.0))
    resp.raise_for_status()
    suffix = os.path.splitext(parsed.path)[1] or ".pdf"
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(tmp, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return tmp


def get_processor_for_file(file_type: str):
    if "pdf" in file_type:
        return PDFProcessor()
    elif "wordprocessingml" in file_type or "msword" in file_type:
        return DOCXProcessor()
    elif "image" in file_type:
        return ImageProcessor()
    elif "text" in file_type:
        return TextProcessor()
    raise ValueError(f"Unsupported file type: {file_type}")


class CallbackTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")
        if args:
            asyncio.run(self._mark_failed(args[0], str(exc)))

    async def _mark_failed(self, document_id: str, error: str):
        from app.utils.redis_client import create_task_redis
        from app.utils.db_pool import connect_prisma_with_timeout, disconnect_prisma_with_timeout
        db = get_prisma()
        redis = create_task_redis()
        await connect_prisma_with_timeout(db, timeout=30)
        try:
            doc = await db.document.find_unique(where={"id": document_id}, include={"job": True})
            if doc and doc.job:
                await db.job.update(where={"id": doc.job.id}, data={
                    "status": "FAILED", "failedAt": datetime.now(), "errorMessage": error
                })
                await db.document.update(where={"id": document_id}, data={"status": "FAILED"})
                await redis.publish(f"progress:{doc.job.id}", {
                    "type": "job_failed", "jobId": doc.job.id, "error": error, "timestamp": time.time()
                })
                await redis.delete(f"job:cancel:{doc.job.id}")
        finally:
            await disconnect_prisma_with_timeout(db, timeout=10)
            try:
                await asyncio.wait_for(redis.close(), timeout=5)
            except Exception:
                pass


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="app.workers.tasks.process_document_task",
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True
)
def process_document_task(self, document_id: str, file_path: str):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_process(self, document_id, file_path))
    finally:
        for t in asyncio.all_tasks(loop):
            t.cancel()
        pending = asyncio.all_tasks(loop)
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


async def _process(task: Task, document_id: str, file_path: str):
    from app.utils.redis_client import create_task_redis
    from app.utils.db_pool import connect_prisma_with_timeout, disconnect_prisma_with_timeout

    db = get_prisma()
    redis = create_task_redis()
    local_path = file_path
    job_id = None

    await connect_prisma_with_timeout(db, timeout=settings.PRISMA_POOL_TIMEOUT)

    try:
        doc = await asyncio.wait_for(
            db.document.find_unique(where={"id": document_id}, include={"job": True}),
            timeout=settings.PRISMA_OPERATION_TIMEOUT
        )

        if not doc or not doc.job:
            raise Exception("Document or job not found")

        job_id = doc.job.id

        # Skip if already in a terminal state
        if doc.status in ("CANCELLED", "COMPLETED"):
            logger.info(f"Document {document_id} already {doc.status}, skipping")
            return {"status": "skipped"}

        # Clear any stale cancellation flag from a previous run
        await redis.delete(f"job:cancel:{job_id}")

        # Check if cancelled before we even start
        if await redis.get(f"job:cancel:{job_id}"):
            await _cancel(db, redis, job_id, document_id)
            return {"status": "cancelled"}

        # --- Stage: Start ---
        await _progress(db, redis, job_id, "job_started", "Starting", 0)
        await db.job.update(where={"id": job_id}, data={"status": "PROCESSING", "startedAt": datetime.now()})
        await db.document.update(where={"id": document_id}, data={"status": "PROCESSING"})

        # --- Stage: Parse ---
        await _progress(db, redis, job_id, "parsing_started", "Parsing document", 10)
        processor = get_processor_for_file(doc.fileType)

        if file_path.startswith("http"):
            local_path = download_remote_file(file_path)

        try:
            parsed = await asyncio.wait_for(processor.parse(local_path), timeout=300)
        except asyncio.TimeoutError:
            raise Exception("Parsing timed out after 5 minutes")

        if not parsed.get("text") or len(parsed["text"].strip()) < 10:
            raise ValueError("No readable text extracted from document")

        await _progress(db, redis, job_id, "parsing_completed", "Parsed", 40)

        # Cancellation checkpoint
        if await redis.get(f"job:cancel:{job_id}"):
            await _cancel(db, redis, job_id, document_id)
            return {"status": "cancelled"}

        # --- Stage: Extract ---
        await _progress(db, redis, job_id, "extraction_started", "Extracting data", 50)
        try:
            extracted = await asyncio.wait_for(processor.extract_structured_data(parsed), timeout=600)
        except asyncio.TimeoutError:
            raise Exception("Extraction timed out after 10 minutes")

        await _progress(db, redis, job_id, "extraction_completed", "Extracted", 90)

        # Cancellation checkpoint
        if await redis.get(f"job:cancel:{job_id}"):
            await _cancel(db, redis, job_id, document_id)
            return {"status": "cancelled"}

        # --- Stage: Store ---
        await _progress(db, redis, job_id, "storing_results", "Saving", 95)
        from prisma import Json as PrismaJson
        meta = extracted.get("metadata")
        create_data = {
            "documentId": document_id,
            "extractedText": extracted.get("text") or "",
            "title": extracted.get("title"),
            "category": extracted.get("category"),
            "summary": extracted.get("summary"),
            "keywords": extracted.get("keywords") or [],
        }
        if meta and isinstance(meta, dict):
            create_data["metadata"] = PrismaJson(meta)

        result = await asyncio.wait_for(
            db.processeddata.create(data=create_data),
            timeout=settings.PRISMA_OPERATION_TIMEOUT
        )

        # --- Stage: Complete ---
        await _progress(db, redis, job_id, "job_completed", "Done", 100)
        await db.job.update(where={"id": job_id}, data={"status": "COMPLETED", "completedAt": datetime.now()})
        await db.document.update(where={"id": document_id}, data={"status": "COMPLETED"})
        await redis.delete(f"job:cancel:{job_id}")

        logger.info(f"Processed document {document_id}")
        return {"status": "completed", "document_id": document_id, "processed_data_id": result.id}

    except Exception as e:
        logger.error(f"Error processing {document_id}: {e}", exc_info=True)
        if job_id:
            try:
                await db.job.update(where={"id": job_id}, data={
                    "status": "FAILED", "failedAt": datetime.now(), "errorMessage": str(e)
                })
                await db.document.update(where={"id": document_id}, data={"status": "FAILED"})
                await _progress(db, redis, job_id, "job_failed", str(e), 0)
            except Exception:
                pass
        raise

    finally:
        if job_id:
            try:
                await redis.delete(f"job:cancel:{job_id}")
            except Exception:
                pass
        if local_path != file_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        from app.utils.db_pool import disconnect_prisma_with_timeout
        await disconnect_prisma_with_timeout(db, timeout=10)
        try:
            await asyncio.wait_for(redis.close(), timeout=5)
        except Exception:
            pass


async def _cancel(db, redis, job_id: str, document_id: str):
    await db.job.update(where={"id": job_id}, data={"status": "CANCELLED"})
    await db.document.update(where={"id": document_id}, data={"status": "CANCELLED"})
    await _progress(db, redis, job_id, "job_cancelled", "Cancelled", 0)
    await redis.delete(f"job:cancel:{job_id}")


async def _progress(db, redis, job_id: str, event_type: str, message: str, progress: int):
    event = {"type": "progress", "jobId": job_id, "eventType": event_type,
             "message": message, "progress": progress, "timestamp": time.time()}
    await redis.publish(f"progress:{job_id}", event)
    await redis.hset(f"job:progress:{job_id}", mapping={
        "status": event_type, "message": message,
        "progress": str(progress), "updated_at": str(time.time())
    })
    await redis.expire(f"job:progress:{job_id}", 3600)
    try:
        await asyncio.wait_for(
            db.progressevent.create(data={"jobId": job_id, "eventType": event_type,
                                          "message": message, "progress": progress}),
            timeout=settings.PRISMA_OPERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        pass
