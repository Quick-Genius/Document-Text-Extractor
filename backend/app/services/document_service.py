from typing import List, Optional, Dict, Any
from fastapi import UploadFile
from app.schemas.document import DocumentResponse, DocumentListResponse, DocumentFilters, PaginationResponse
from app.services.storage_service import StorageService
from app.workers.tasks import process_document_task
from app.utils.exceptions import NotFoundError, PermissionError
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from app.core.config import settings

def get_prisma():
    from prisma import Prisma
    return Prisma()

class DocumentService:
    def __init__(self):
        self.storage = StorageService()
    
    async def create_documents_from_upload(
        self,
        user_id: str,
        files: List[UploadFile],
        category: Optional[str] = None
    ) -> List[DocumentResponse]:
        """
        Process file uploads and create database records
        """
        db = get_prisma()
        await db.connect()
        
        try:
            documents = []

            # Ensure user exists
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                # Create user if doesn't exist
                user = await db.user.create(
                    data={
                        "clerkId": user_id,
                        "email": f"{user_id}@temp.com",  # Temporary email
                    }
                )

            for file in files:
                file_id = str(uuid.uuid4())
                file_ext = file.filename.split('.')[-1] if '.' in file.filename else ''
                stored_filename = f"{file_id}.{file_ext}" if file_ext else file_id

                # Persist file to storage
                file_path = await self.storage.save_file(
                    file=file,
                    filename=stored_filename,
                    folder="uploads"
                )

                # Create document in database
                document = await db.document.create(
                    data={
                        "userId": user.id,
                        "filename": stored_filename,
                        "originalName": file.filename,
                        "fileType": file.content_type,
                        "fileSize": file.size or 0,
                        "filePath": file_path,
                        "status": "PENDING",
                    }
                )

                # Create job for the document
                job = await db.job.create(
                    data={
                        "documentId": document.id,
                        "celeryTaskId": str(uuid.uuid4()),  # Temporary, will be updated
                        "status": "PENDING",
                    }
                )

                # Enqueue document processing task
                task_result = process_document_task.delay(document_id=document.id, file_path=file_path)
                
                # Update job with actual Celery task ID
                await db.job.update(
                    where={"id": job.id},
                    data={"celeryTaskId": task_result.id}
                )
                
                logger.info(f"Enqueued processing task for document {document.id}, task_id: {task_result.id}")

                # Fetch document with job for response
                doc_with_job = await db.document.find_unique(
                    where={"id": document.id},
                    include={"job": True}
                )
                
                documents.append(DocumentResponse(
                    id=doc_with_job.id,
                    userId=doc_with_job.userId,
                    filename=doc_with_job.filename,
                    originalName=doc_with_job.originalName,
                    fileType=doc_with_job.fileType,
                    fileSize=doc_with_job.fileSize,
                    filePath=doc_with_job.filePath,
                    status=doc_with_job.status,
                    uploadedAt=doc_with_job.uploadedAt,
                    updatedAt=doc_with_job.updatedAt,
                    job={
                        "id": doc_with_job.job.id,
                        "documentId": doc_with_job.job.documentId,
                        "celeryTaskId": doc_with_job.job.celeryTaskId,
                        "status": doc_with_job.job.status,
                        "createdAt": doc_with_job.job.createdAt,
                        "updatedAt": doc_with_job.job.updatedAt,
                    } if doc_with_job.job else None
                ))

            return documents

        except Exception as e:
            logger.error(f"Upload processing error: {e}", exc_info=True)
            raise
        finally:
            await db.disconnect()

    async def list_documents(
        self,
        user_id: str,
        filters: DocumentFilters
    ) -> DocumentListResponse:
        """
        List documents from database
        """
        db = get_prisma()
        await db.connect()
        
        try:
            # Get user
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                return DocumentListResponse(
                    documents=[],
                    pagination=PaginationResponse(total=0, page=1, limit=filters.limit, pages=0)
                )

            # Build where clause
            where = {"userId": user.id}
            if filters.status:
                where["status"] = filters.status
            if filters.search:
                where["originalName"] = {"contains": filters.search, "mode": "insensitive"}

            # Get total count
            total = await db.document.count(where=where)

            # Get documents
            documents = await db.document.find_many(
                where=where,
                include={"job": True},
                order={filters.sort_by: filters.order},
                skip=(filters.page - 1) * filters.limit,
                take=filters.limit
            )

            doc_responses = []
            for doc in documents:
                doc_responses.append(DocumentResponse(
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
                    job={
                        "id": doc.job.id,
                        "documentId": doc.job.documentId,
                        "celeryTaskId": doc.job.celeryTaskId,
                        "status": doc.job.status,
                        "createdAt": doc.job.createdAt,
                        "updatedAt": doc.job.updatedAt,
                    } if doc.job else None
                ))

            return DocumentListResponse(
                documents=doc_responses,
                pagination=PaginationResponse(
                    total=total,
                    page=filters.page,
                    limit=filters.limit,
                    pages=(total + filters.limit - 1) // filters.limit
                )
            )
        finally:
            await db.disconnect()

    async def get_document_by_id(self, document_id: str, user_id: str) -> Optional[DocumentResponse]:
        """Retrieve document from database"""
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

            # Build processedData response if it exists
            processed_data_response = None
            if doc.processedData:
                processed_data_response = {
                    "id": doc.processedData.id,
                    "extractedText": doc.processedData.extractedText,
                    "title": doc.processedData.title,
                    "category": doc.processedData.category,
                    "summary": doc.processedData.summary,
                    "keywords": doc.processedData.keywords,
                    "metadata": doc.processedData.metadata,
                    "confidenceScore": doc.processedData.confidenceScore,
                    "isReviewed": doc.processedData.isReviewed,
                    "isFinalized": doc.processedData.isFinalized,
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
                job={
                    "id": doc.job.id,
                    "documentId": doc.job.documentId,
                    "celeryTaskId": doc.job.celeryTaskId,
                    "status": doc.job.status,
                    "createdAt": doc.job.createdAt,
                    "updatedAt": doc.job.updatedAt,
                } if doc.job else None,
                processedData=processed_data_response
            )
        finally:
            await db.disconnect()

    async def delete_document(self, document_id: str, user_id: str) -> None:
        """Mock implementation - does nothing"""
        pass

    async def update_processed_data(self, document_id: str, user_id: str, data: dict) -> dict:
        """Mock implementation - returns the data"""
        return data

    async def finalize_document(self, document_id: str, user_id: str) -> dict:
        """Mock implementation - returns empty dict"""
        return {}

    async def process_document(self, document_id: str, user_id: str) -> dict:
        """
        Trigger AI processing on a single uploaded document.
        In production this would enqueue a Celery task.
        """
        logger.info(f"Processing document {document_id} for user {user_id}")
        
        # Mock: In production, this would:
        # 1. Validate the document exists and belongs to user
        # 2. Update document status to PROCESSING
        # 3. Enqueue a Celery task for AI extraction
        # process_document_task.delay(document_id)
        
        return {
            "id": document_id,
            "status": "PROCESSING",
            "message": "Document has been queued for AI processing"
        }

    async def process_documents_batch(self, document_ids: list, user_id: str) -> list:
        """
        Trigger AI processing on multiple uploaded documents.
        """
        logger.info(f"Batch processing {len(document_ids)} documents for user {user_id}")
        
        results = []
        for doc_id in document_ids:
            result = await self.process_document(doc_id, user_id)
            results.append(result)
        
        return results


    async def cancel_document(self, document_id: str, user_id: str) -> DocumentResponse:
        """Cancel a document that is currently processing or queued"""
        from app.utils.redis_client import redis_client
        import time
        
        db = get_prisma()
        await db.connect()
        
        try:
            # Get user
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                raise PermissionError("User not found")
            
            # Get document with job
            document = await db.document.find_first(
                where={"id": document_id, "userId": user.id},
                include={"job": True}
            )
            
            if not document:
                raise NotFoundError("Document not found")
            
            # Validate status
            if document.status not in ["PROCESSING", "QUEUED"]:
                raise ValidationError("Document is not in a cancellable state")
            
            # Set cancellation flag in Redis
            await redis_client.set(f"job:cancel:{document.job.id}", "1", ex=3600)
            
            # Update job status
            await db.job.update(
                where={"id": document.job.id},
                data={"status": "CANCELLED"}
            )
            
            # Update document status
            await db.document.update(
                where={"id": document_id},
                data={"status": "CANCELLED"}
            )
            
            # Publish cancellation event
            await redis_client.publish(
                f"progress:{document.job.id}",
                {
                    "type": "job_cancelled",
                    "jobId": document.job.id,
                    "timestamp": time.time()
                }
            )
            
            # Fetch updated document
            updated_doc = await db.document.find_unique(
                where={"id": document_id},
                include={"job": True}
            )
            
            return DocumentResponse(
                id=updated_doc.id,
                userId=updated_doc.userId,
                filename=updated_doc.filename,
                originalName=updated_doc.originalName,
                fileType=updated_doc.fileType,
                fileSize=updated_doc.fileSize,
                filePath=updated_doc.filePath,
                status=updated_doc.status,
                uploadedAt=updated_doc.uploadedAt,
                updatedAt=updated_doc.updatedAt,
                job={
                    "id": updated_doc.job.id,
                    "documentId": updated_doc.job.documentId,
                    "celeryTaskId": updated_doc.job.celeryTaskId,
                    "status": updated_doc.job.status,
                    "createdAt": updated_doc.job.createdAt,
                    "updatedAt": updated_doc.job.updatedAt,
                } if updated_doc.job else None
            )
        finally:
            await db.disconnect()

    async def retry_document(self, document_id: str, user_id: str) -> DocumentResponse:
        """Retry processing for a failed document"""
        import os
        
        db = get_prisma()
        await db.connect()
        
        try:
            # Get user
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                raise PermissionError("User not found")
            
            # Get document with job and processed data
            document = await db.document.find_first(
                where={"id": document_id, "userId": user.id},
                include={"job": True, "processedData": True}
            )
            
            if not document:
                raise NotFoundError("Document not found")
            
            # Validate status
            if document.status != "FAILED":
                raise ValidationError("Only failed documents can be retried")
            
            # Check retry limit
            if document.job.retryCount >= document.job.maxRetries:
                raise ValidationError("Maximum retry attempts exceeded")
            
            # Verify file exists
            file_path = document.filePath
            if file_path.startswith("http"):
                # S3 file - assume it exists (will fail during processing if not)
                pass
            else:
                # Local file - check existence
                if not os.path.exists(file_path):
                    raise ValidationError("Original file not found, please re-upload")
            
            # Delete existing processed data
            if document.processedData:
                await db.processeddata.delete(where={"id": document.processedData.id})
            
            # Update job
            await db.job.update(
                where={"id": document.job.id},
                data={
                    "status": "PENDING",
                    "retryCount": document.job.retryCount + 1,
                    "errorMessage": None,
                    "failedAt": None
                }
            )
            
            # Update document
            await db.document.update(
                where={"id": document_id},
                data={"status": "PENDING"}
            )
            
            # Enqueue new task
            task_result = process_document_task.delay(
                document_id=document_id,
                file_path=file_path
            )
            
            # Update job with new task ID
            await db.job.update(
                where={"id": document.job.id},
                data={"celeryTaskId": task_result.id}
            )
            
            # Fetch updated document
            updated_doc = await db.document.find_unique(
                where={"id": document_id},
                include={"job": True}
            )
            
            return DocumentResponse(
                id=updated_doc.id,
                userId=updated_doc.userId,
                filename=updated_doc.filename,
                originalName=updated_doc.originalName,
                fileType=updated_doc.fileType,
                fileSize=updated_doc.fileSize,
                filePath=updated_doc.filePath,
                status=updated_doc.status,
                uploadedAt=updated_doc.uploadedAt,
                updatedAt=updated_doc.updatedAt,
                job={
                    "id": updated_doc.job.id,
                    "documentId": updated_doc.job.documentId,
                    "celeryTaskId": updated_doc.job.celeryTaskId,
                    "status": updated_doc.job.status,
                    "retryCount": updated_doc.job.retryCount,
                    "maxRetries": updated_doc.job.maxRetries,
                    "createdAt": updated_doc.job.createdAt,
                    "updatedAt": updated_doc.job.updatedAt,
                } if updated_doc.job else None
            )
        finally:
            await db.disconnect()
