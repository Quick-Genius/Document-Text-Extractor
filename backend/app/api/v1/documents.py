from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status as http_status, Form, Request
from pydantic import BaseModel
from typing import List, Optional
from app.core.auth import get_current_user_id
from app.services.document_service import DocumentService
from app.schemas.document import DocumentResponse, DocumentListResponse, DocumentFilters
from app.utils.exceptions import StorageError, ValidationError, AccessDeniedError
import logging
import os

router = APIRouter()
logger = logging.getLogger(__name__)

def get_document_service(request: Request) -> DocumentService:
    """Dependency to get DocumentService with scheduler"""
    scheduler = getattr(request.app.state, 'scheduler', None)
    return DocumentService(scheduler=scheduler)

class DashboardStats(BaseModel):
    active_jobs: int
    storage_used_mb: float
    success_rate: float

@router.post("/documents/upload", response_model=DocumentListResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Upload one or more documents for processing
    
    - **files**: List of files to upload (max 10 files)
    - **category**: Optional category for documents
    
    Returns list of created documents with job information
    
    Rate Limiting:
    - Batch uploads (2+ files) are subject to queue depth limits
    - Returns 429 Too Many Requests if system is overloaded
    """
    try:
        
        # Validate file count
        if len(files) > 10:
            raise ValidationError("Maximum 10 files per upload")
        
        # Validate each file
        for file in files:
            # Check file size
            if file.size > 50 * 1024 * 1024:  # 50MB
                raise ValidationError(f"File {file.filename} exceeds 50MB limit")
            
            # Check file type
            allowed_types = [
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain',
                'image/jpeg',
                'image/png',
                'text/csv',
                'text/html'
            ]
            
            if file.content_type not in allowed_types:
                raise ValidationError(f"File type {file.content_type} not supported")
        
        # Process uploads
        documents = await document_service.create_documents_from_upload(
            user_id=user_id,
            files=files,
            category=category
        )
        
        logger.info(f"User {user_id} uploaded {len(documents)} documents")
        
        return DocumentListResponse(documents=documents)
        
    except ValidationError as e:
        # Check if this is a rate limiting error
        error_msg = str(e)
        if "queue depth" in error_msg.lower() or "maximum queue depth" in error_msg.lower():
            # Return 429 Too Many Requests for rate limiting
            raise HTTPException(
                status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg,
                headers={"Retry-After": "60"}  # Suggest retry after 60 seconds
            )
        else:
            # Regular validation error
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except StorageError as e:
        logger.error(f"Storage error: {e}")
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store file")
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "uploadedAt",
    order: str = "desc",
    page: int = 1,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    List user's documents with filtering and pagination
    """
    try:
        filters = DocumentFilters(
            status=status,
            search=search,
            sort_by=sort_by,
            order=order,
            page=page,
            limit=limit
        )
        
        result = await document_service.list_documents(user_id, filters)
        
        return result
        
    except Exception as e:
        logger.error(f"List documents error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch documents")

@router.get("/documents/stats/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get dashboard statistics: active jobs, storage used, and success rate
    """
    try:
        # Get all user documents
        filters = DocumentFilters(
            status=None,
            search=None,
            sort_by="uploadedAt",
            order="desc",
            page=1,
            limit=1000
        )
        result = await document_service.list_documents(user_id, filters)
        documents = result.documents
        
        # Calculate active jobs (QUEUED + PROCESSING)
        active_jobs = sum(1 for doc in documents if doc.status in ['QUEUED', 'PROCESSING'])
        
        # Calculate storage used
        storage_used_bytes = sum(doc.fileSize for doc in documents)
        storage_used_mb = storage_used_bytes / (1024 * 1024)
        
        # Calculate success rate
        total_completed = sum(1 for doc in documents if doc.status == 'COMPLETED')
        total_documents = len(documents)
        success_rate = (total_completed / total_documents * 100) if total_documents > 0 else 0
        
        return DashboardStats(
            active_jobs=active_jobs,
            storage_used_mb=round(storage_used_mb, 2),
            success_rate=round(success_rate, 1)
        )
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch dashboard stats")

@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get document details including processed data
    """
    try:
        document = await document_service.get_document_by_id(document_id, user_id)
        
        if not document:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Document not found")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch document")

@router.delete("/documents/{document_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    permanent: bool = False,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Delete a document and its associated data
    """
    try:
        await document_service.delete_document(document_id, user_id, permanent)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete document")

@router.put("/documents/{document_id}/processed-data")
async def update_processed_data(
    document_id: str,
    data: dict,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Update processed data for a document
    """
    try:
        updated = await document_service.update_processed_data(document_id, user_id, data)
        
        return updated
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update processed data error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update data")

@router.post("/documents/{document_id}/finalize")
async def finalize_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Finalize a document (locks it from further edits)
    """
    try:
        finalized = await document_service.finalize_document(document_id, user_id)
        
        return finalized
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Finalize document error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to finalize document")


class ProcessBatchRequest(BaseModel):
    document_ids: List[str]


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Trigger AI processing on a single uploaded document
    """
    try:
        result = await document_service.process_document(document_id, user_id)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process document error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process document")


@router.post("/documents/process-batch")
async def process_documents_batch(
    request: ProcessBatchRequest,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Trigger AI processing on multiple uploaded documents
    """
    try:
        if len(request.document_ids) == 0:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="No document IDs provided")
        
        if len(request.document_ids) > 10:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Maximum 10 documents per batch")
        
        results = await document_service.process_documents_batch(request.document_ids, user_id)
        
        return {"documents": results, "processed": len(results)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch process error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process documents")


@router.post("/documents/{document_id}/cancel")
async def cancel_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Cancel a document that is currently processing or queued
    """
    try:
        result = await document_service.cancel_document(document_id, user_id)
        
        return {
            "id": result.id,
            "status": result.status,
            "message": "Document processing cancelled successfully"
        }
        
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Cancel document error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cancel document")


@router.post("/documents/{document_id}/retry")
async def retry_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Retry processing for a document
    
    Supports restarting:
    - FAILED documents (increments retry count)
    - CANCELLED documents (reprocesses from scratch)
    - COMPLETED documents (reprocesses from scratch)
    """
    try:
        result = await document_service.retry_document(document_id, user_id)
        
        return {
            "id": result.id,
            "status": result.status,
            "job": result.job,
            "message": "Document queued for retry"
        }
        
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Retry document error: {e}", exc_info=True)
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retry document")


@router.get("/documents/{document_id}/preview")
async def preview_document(
    document_id: str,
    token: Optional[str] = None,
    download: bool = False,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get document file for preview
    
    Returns the actual document file for preview in the browser.
    Supports PDF, images, and text files.
    Proxies S3 files to avoid CORS issues.
    
    Can be accessed with Bearer token in header or ?token=xxx in query string.
    """
    from fastapi.responses import FileResponse, StreamingResponse
    from app.utils.db_pool import get_prisma_with_pool
    import httpx
    
    try:
        # Get document from database
        db = get_prisma_with_pool()
        await db.connect()
        
        try:
            # Get user
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                logger.error(f"User not found: {user_id}")
                raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found")
            
            # Get document
            document = await db.document.find_first(
                where={"id": document_id, "userId": user.id}
            )
            
            if not document:
                logger.error(f"Document not found: {document_id} for user {user_id}")
                raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Document not found")
            
            file_path = document.filePath
            logger.info(f"Preview requested for document {document_id}, file_path: {file_path}")
            
            # Handle S3 URLs - proxy through backend to avoid CORS issues
            if file_path.startswith("http"):
                logger.info(f"Proxying S3 file: {file_path}")
                
                async def stream_s3_file():
                    async with httpx.AsyncClient() as client:
                        async with client.stream('GET', file_path) as response:
                            response.raise_for_status()
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                yield chunk
                
                # Determine media type
                media_type = document.fileType or "application/octet-stream"
                disposition = f"attachment; filename=\"{document.originalName}\"" if download else f"inline; filename=\"{document.originalName}\""
                
                return StreamingResponse(
                    stream_s3_file(),
                    media_type=media_type,
                    headers={
                        "Content-Disposition": disposition,
                        "Cache-Control": "public, max-age=3600",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, OPTIONS",
                        "Access-Control-Allow-Headers": "*"
                    }
                )
            
            # Handle local files
            if not os.path.exists(file_path):
                logger.error(f"File not found on server: {file_path}")
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND, 
                    detail=f"File not found on server"
                )
            
            # Determine media type
            media_type = document.fileType or "application/octet-stream"
            logger.info(f"Serving file: {file_path}, media_type: {media_type}")
            disposition = f"attachment; filename=\"{document.originalName}\"" if download else f"inline; filename=\"{document.originalName}\""

            # Return file with appropriate headers for preview or download
            return FileResponse(
                path=file_path,
                media_type=media_type,
                filename=document.originalName,
                headers={"Content-Disposition": disposition}
            )
        finally:
            await db.disconnect()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview document error: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to load document preview: {str(e)}"
        )
