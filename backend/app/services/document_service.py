import uuid
import os
import logging
import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import UploadFile

from app.schemas.document import DocumentResponse, DocumentListResponse, DocumentFilters, PaginationResponse
from app.services.storage_service import StorageService
from app.workers.tasks import process_document_task
from app.utils.exceptions import NotFoundError, AccessDeniedError, ValidationError
from app.core.config import settings
from app.utils.db_pool import get_prisma_with_pool

logger = logging.getLogger(__name__)


def get_prisma():
    return get_prisma_with_pool()


def _doc_response(doc, job_extra: dict = None) -> DocumentResponse:
    """Build a DocumentResponse from a Prisma document record."""
    job = None
    if doc.job:
        job = {
            "id": doc.job.id,
            "documentId": doc.job.documentId,
            "celeryTaskId": doc.job.celeryTaskId,
            "status": doc.job.status,
            "retryCount": getattr(doc.job, "retryCount", 0),
            "maxRetries": getattr(doc.job, "maxRetries", 3),
            "createdAt": doc.job.createdAt,
            "updatedAt": doc.job.updatedAt,
        }
        if job_extra:
            job.update(job_extra)

    processed_data = None
    if getattr(doc, "processedData", None):
        pd = doc.processedData
        processed_data = {
            "id": pd.id,
            "extractedText": pd.extractedText,
            "title": pd.title,
            "category": pd.category,
            "summary": pd.summary,
            "keywords": pd.keywords,
            "metadata": pd.metadata,
            "confidenceScore": pd.confidenceScore,
            "isReviewed": pd.isReviewed,
            "isFinalized": pd.isFinalized,
        }

    return DocumentResponse(
        id=doc.id,
        userId=doc.userId,
        filename=doc.filename,
        originalName=doc.originalName,
        fileType=doc.fileType,
        fileSize=doc.fileSize,
        filePath=doc.filePath,
        status=doc.status,
        uploadedAt=doc.uploadedAt,
        updatedAt=doc.updatedAt,
        job=job,
        processedData=processed_data,
    )


async def _get_file_size(file_path: str, file_size_hint: int) -> int:
    """Return actual file size, falling back to S3/disk lookup if needed."""
    if file_size_hint and file_size_hint > 0:
        return file_size_hint
    try:
        if file_path.startswith("http"):
            import boto3
            from urllib.parse import urlparse
            parsed = urlparse(file_path)
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
            return s3.head_object(Bucket=bucket, Key=key)['ContentLength']
        elif os.path.exists(file_path):
            return os.path.getsize(file_path)
    except Exception as e:
        logger.warning(f"Could not determine file size for {file_path}: {e}")
    return 0


def _enqueue(document_id: str, file_path: str) -> str:
    """Generate a task ID, then enqueue via apply_async. Returns task_id."""
    task_id = str(uuid.uuid4())
    process_document_task.apply_async(args=[document_id, file_path], task_id=task_id)
    return task_id


class DocumentService:
    def __init__(self, scheduler=None):
        self.storage = StorageService()
        self.scheduler = scheduler

    async def _get_or_create_user(self, db, user_id: str):
        user = await db.user.find_unique(where={"clerkId": user_id})
        if not user:
            user = await db.user.create(data={"clerkId": user_id, "email": f"{user_id}@temp.com"})
        return user

    async def create_documents_from_upload(
        self,
        user_id: str,
        files: List[UploadFile],
        category: Optional[str] = None
    ) -> List[DocumentResponse]:
        db = get_prisma()
        await db.connect()
        try:
            user = await self._get_or_create_user(db, user_id)

            # Queue depth guard for batch uploads
            if len(files) >= 2:
                depth = await db.document.count(where={"status": {"in": ["PENDING", "QUEUED", "PROCESSING"]}})
                if depth >= settings.BATCH_UPLOAD_MAX_QUEUE_DEPTH:
                    raise ValidationError(
                        f"System is busy ({depth} documents queued). "
                        f"Max queue depth: {settings.BATCH_UPLOAD_MAX_QUEUE_DEPTH}"
                    )

            # Step 1: Upload all files to storage (outside DB transaction)
            uploads = []
            for file in files:
                file_id = str(uuid.uuid4())
                ext = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else ''
                stored_name = f"{file_id}.{ext}" if ext else file_id
                file_path = await self.storage.save_file(file=file, filename=stored_name, folder="uploads")
                size = await _get_file_size(file_path, file.size or 0)
                uploads.append({"file": file, "stored_name": stored_name, "file_path": file_path, "size": size})

            # Step 2: Create DB records (short transaction, no I/O)
            created = []
            from datetime import timedelta
            async with db.tx(timeout=timedelta(seconds=30)) as tx:
                for u in uploads:
                    doc = await tx.document.create(data={
                        "userId": user.id,
                        "filename": u["stored_name"],
                        "originalName": u["file"].filename,
                        "fileType": u["file"].content_type,
                        "fileSize": u["size"],
                        "filePath": u["file_path"],
                        "status": "PENDING",
                    })
                    job = await tx.job.create(data={
                        "documentId": doc.id,
                        "celeryTaskId": str(uuid.uuid4()),  # placeholder
                        "status": "PENDING",
                    })
                    created.append({"doc_id": doc.id, "job_id": job.id, "file_path": u["file_path"]})

            # Step 3: Enqueue each task (update DB to QUEUED first, then dispatch)
            for c in created:
                try:
                    task_id = str(uuid.uuid4())
                    await db.job.update(where={"id": c["job_id"]}, data={"celeryTaskId": task_id, "status": "QUEUED"})
                    await db.document.update(where={"id": c["doc_id"]}, data={"status": "QUEUED"})
                    process_document_task.apply_async(args=[c["doc_id"], c["file_path"]], task_id=task_id)
                    logger.info(f"Enqueued document {c['doc_id']} task {task_id}")
                except Exception as e:
                    logger.error(f"Failed to enqueue {c['doc_id']}: {e}")
                    await db.document.update(where={"id": c["doc_id"]}, data={"status": "FAILED"})
                    await db.job.update(where={"id": c["job_id"]}, data={
                        "status": "FAILED", "failedAt": datetime.now(), "errorMessage": str(e)
                    })

            # Fetch and return all documents
            docs = []
            for c in created:
                doc = await db.document.find_unique(where={"id": c["doc_id"]}, include={"job": True})
                docs.append(_doc_response(doc))
            return docs

        except Exception as e:
            logger.error(f"Upload error: {e}", exc_info=True)
            raise
        finally:
            await db.disconnect()

    async def list_documents(self, user_id: str, filters: DocumentFilters) -> DocumentListResponse:
        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                return DocumentListResponse(
                    documents=[],
                    pagination=PaginationResponse(total=0, page=1, limit=filters.limit, pages=0)
                )

            where = {"userId": user.id}
            if filters.status:
                where["status"] = {"in": filters.status.split(",")} if "," in filters.status else filters.status
            if filters.search:
                where["originalName"] = {"contains": filters.search, "mode": "insensitive"}

            total = await db.document.count(where=where)
            docs = await db.document.find_many(
                where=where,
                include={"job": True},
                order={filters.sort_by: filters.order},
                skip=(filters.page - 1) * filters.limit,
                take=filters.limit
            )

            responses = []
            for doc in docs:
                r = _doc_response(doc)
                if doc.status == 'PENDING':
                    r.queuePosition = await db.document.count(
                        where={"status": "PENDING", "uploadedAt": {"lt": doc.uploadedAt}}
                    ) + 1
                responses.append(r)

            return DocumentListResponse(
                documents=responses,
                pagination=PaginationResponse(
                    total=total, page=filters.page, limit=filters.limit,
                    pages=(total + filters.limit - 1) // filters.limit
                )
            )
        finally:
            await db.disconnect()

    async def get_document_by_id(self, document_id: str, user_id: str) -> Optional[DocumentResponse]:
        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                return None
            doc = await db.document.find_first(
                where={"id": document_id, "userId": user.id},
                include={"job": True, "processedData": True}
            )
            if not doc:
                return None
            r = _doc_response(doc)
            if doc.status == 'PENDING':
                r.queuePosition = await db.document.count(
                    where={"status": "PENDING", "uploadedAt": {"lt": doc.uploadedAt}}
                ) + 1
            return r
        finally:
            await db.disconnect()

    async def delete_document(self, document_id: str, user_id: str, permanent: bool = False) -> None:
        from app.workers.celery_app import celery_app
        from app.utils.redis_client import redis_client

        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                raise AccessDeniedError("User not found")
            doc = await db.document.find_first(
                where={"id": document_id, "userId": user.id}, include={"job": True}
            )
            if not doc:
                raise NotFoundError("Document not found")

            # Revoke active task
            if doc.job and doc.status in ("PENDING", "QUEUED", "PROCESSING"):
                celery_app.control.revoke(doc.job.celeryTaskId, terminate=True, signal='SIGKILL')
                await redis_client.set(f"job:cancel:{doc.job.id}", "1", ex=60)
                await db.job.update(where={"id": doc.job.id}, data={"status": "CANCELLED"})
                await redis_client.delete(f"job:cancel:{doc.job.id}")

            if doc.filePath:
                await self.storage.delete_file(doc.filePath)

            if permanent:
                await db.document.delete(where={"id": document_id})
            else:
                await db.document.update(where={"id": document_id}, data={"filePath": "", "status": "CANCELLED"})

            if self.scheduler:
                await self.scheduler.trigger_immediate_check()
        finally:
            await db.disconnect()

    async def cancel_document(self, document_id: str, user_id: str) -> DocumentResponse:
        from app.workers.celery_app import celery_app
        from app.utils.redis_client import redis_client
        import time

        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                raise AccessDeniedError("User not found")
            doc = await db.document.find_first(
                where={"id": document_id, "userId": user.id}, include={"job": True}
            )
            if not doc:
                raise NotFoundError("Document not found")
            if doc.status not in ("PROCESSING", "QUEUED", "PENDING"):
                raise ValidationError("Document is not in a cancellable state")

            celery_app.control.revoke(doc.job.celeryTaskId, terminate=True, signal='SIGKILL')
            await redis_client.set(f"job:cancel:{doc.job.id}", "1", ex=60)
            await db.job.update(where={"id": doc.job.id}, data={"status": "CANCELLED"})
            await db.document.update(where={"id": document_id}, data={"status": "CANCELLED"})
            await redis_client.delete(f"job:cancel:{doc.job.id}")
            await redis_client.publish(f"progress:{doc.job.id}", {
                "type": "job_cancelled", "jobId": doc.job.id, "timestamp": time.time()
            })

            updated = await db.document.find_unique(where={"id": document_id}, include={"job": True})
            if self.scheduler:
                await self.scheduler.trigger_immediate_check()
            return _doc_response(updated)
        finally:
            await db.disconnect()

    async def retry_document(self, document_id: str, user_id: str) -> DocumentResponse:
        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                raise AccessDeniedError("User not found")
            doc = await db.document.find_first(
                where={"id": document_id, "userId": user.id},
                include={"job": True, "processedData": True}
            )
            if not doc:
                raise NotFoundError("Document not found")
            if doc.status not in ("FAILED", "CANCELLED", "COMPLETED"):
                raise ValidationError("Only failed, cancelled, or completed documents can be restarted")
            if doc.status == "FAILED" and doc.job.retryCount >= doc.job.maxRetries:
                raise ValidationError("Maximum retry attempts exceeded")

            file_path = doc.filePath
            if not file_path.startswith("http") and not os.path.exists(file_path):
                raise ValidationError("Original file not found, please re-upload")

            if doc.processedData:
                await db.processeddata.delete(where={"id": doc.processedData.id})

            new_retry = doc.job.retryCount + 1 if doc.status == "FAILED" else doc.job.retryCount
            task_id = str(uuid.uuid4())

            await db.job.update(where={"id": doc.job.id}, data={
                "status": "QUEUED", "celeryTaskId": task_id,
                "retryCount": new_retry, "errorMessage": None, "failedAt": None
            })
            await db.document.update(where={"id": document_id}, data={"status": "QUEUED"})
            process_document_task.apply_async(args=[document_id, file_path], task_id=task_id)

            updated = await db.document.find_unique(where={"id": document_id}, include={"job": True})
            if self.scheduler:
                await self.scheduler.trigger_immediate_check()
            return _doc_response(updated)
        finally:
            await db.disconnect()

    async def update_processed_data(self, document_id: str, user_id: str, data: dict) -> dict:
        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                raise AccessDeniedError("User not found")
            doc = await db.document.find_first(
                where={"id": document_id, "userId": user.id},
                include={"processedData": True}
            )
            if not doc:
                raise NotFoundError("Document not found")
            if not doc.processedData:
                raise ValidationError("No processed data to update")
            updated = await db.processeddata.update(
                where={"id": doc.processedData.id},
                data={k: v for k, v in data.items() if k not in ("id", "documentId")}
            )
            return {"id": updated.id, "message": "Updated successfully"}
        finally:
            await db.disconnect()

    async def finalize_document(self, document_id: str, user_id: str) -> dict:
        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                raise AccessDeniedError("User not found")
            doc = await db.document.find_first(
                where={"id": document_id, "userId": user.id},
                include={"processedData": True}
            )
            if not doc or not doc.processedData:
                raise NotFoundError("Document or processed data not found")
            await db.processeddata.update(
                where={"id": doc.processedData.id}, data={"isFinalized": True}
            )
            return {"id": document_id, "message": "Finalized"}
        finally:
            await db.disconnect()

    async def process_document(self, document_id: str, user_id: str) -> dict:
        """Manually trigger processing for an already-uploaded document."""
        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                raise AccessDeniedError("User not found")
            doc = await db.document.find_first(
                where={"id": document_id, "userId": user.id}, include={"job": True}
            )
            if not doc:
                raise NotFoundError("Document not found")

            task_id = str(uuid.uuid4())
            await db.job.update(where={"id": doc.job.id}, data={"celeryTaskId": task_id, "status": "QUEUED"})
            await db.document.update(where={"id": document_id}, data={"status": "QUEUED"})
            process_document_task.apply_async(args=[document_id, doc.filePath], task_id=task_id)
            return {"id": document_id, "status": "QUEUED"}
        finally:
            await db.disconnect()

    async def process_documents_batch(self, document_ids: list, user_id: str) -> list:
        return [await self.process_document(doc_id, user_id) for doc_id in document_ids]
