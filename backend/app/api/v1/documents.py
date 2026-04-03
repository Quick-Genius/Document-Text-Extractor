from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Form
from pydantic import BaseModel
from typing import List, Optional
from app.core.auth import get_current_user_id
from app.services.document_service import DocumentService
from app.schemas.document import DocumentResponse, DocumentListResponse, DocumentFilters
from app.utils.exceptions import StorageError, ValidationError
import logging
import os

router = APIRouter()
logger = logging.getLogger(__name__)

class DashboardStats(BaseModel):
    active_jobs: int
    storage_used_mb: float
    success_rate: float

@router.post("/documents/upload", response_model=DocumentListResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id)
):
    """
    Upload one or more documents for processing
    
    - **files**: List of files to upload (max 10 files)
    - **category**: Optional category for documents
    
    Returns list of created documents with job information
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
        document_service = DocumentService()
        documents = await document_service.create_documents_from_upload(
            user_id=user_id,
            files=files,
            category=category
        )
        
        logger.info(f"User {user_id} uploaded {len(documents)} documents")
        
        return DocumentListResponse(documents=documents)
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except StorageError as e:
        logger.error(f"Storage error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store file")
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "uploadedAt",
    order: str = "desc",
    page: int = 1,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id)
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
        
        document_service = DocumentService()
        result = await document_service.list_documents(user_id, filters)
        
        return result
        
    except Exception as e:
        logger.error(f"List documents error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch documents")

@router.get("/documents/stats/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    user_id: str = Depends(get_current_user_id)
):
    """
    Get dashboard statistics: active jobs, storage used, and success rate
    """
    try:
        document_service = DocumentService()
        
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch dashboard stats")

@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get document details including processed data
    """
    try:
        document_service = DocumentService()
        document = await document_service.get_document_by_id(document_id, user_id)
        
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch document")

@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a document and its associated data
    """
    try:
        document_service = DocumentService()
        await document_service.delete_document(document_id, user_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete document")

@router.put("/documents/{document_id}/processed-data")
async def update_processed_data(
    document_id: str,
    data: dict,
    user_id: str = Depends(get_current_user_id)
):
    """
    Update processed data for a document
    """
    try:
        document_service = DocumentService()
        updated = await document_service.update_processed_data(document_id, user_id, data)
        
        return updated
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update processed data error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update data")

@router.post("/documents/{document_id}/finalize")
async def finalize_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Finalize a document (locks it from further edits)
    """
    try:
        document_service = DocumentService()
        finalized = await document_service.finalize_document(document_id, user_id)
        
        return finalized
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Finalize document error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to finalize document")


class ProcessBatchRequest(BaseModel):
    document_ids: List[str]


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Trigger AI processing on a single uploaded document
    """
    try:
        document_service = DocumentService()
        result = await document_service.process_document(document_id, user_id)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process document error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process document")


@router.post("/documents/process-batch")
async def process_documents_batch(
    request: ProcessBatchRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Trigger AI processing on multiple uploaded documents
    """
    try:
        if len(request.document_ids) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No document IDs provided")
        
        if len(request.document_ids) > 10:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 10 documents per batch")
        
        document_service = DocumentService()
        results = await document_service.process_documents_batch(request.document_ids, user_id)
        
        return {"documents": results, "processed": len(results)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch process error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process documents")


@router.post("/documents/{document_id}/cancel")
async def cancel_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Cancel a document that is currently processing or queued
    """
    try:
        document_service = DocumentService()
        result = await document_service.cancel_document(document_id, user_id)
        
        return {
            "id": result.id,
            "status": result.status,
            "message": "Document processing cancelled successfully"
        }
        
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Cancel document error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cancel document")


@router.post("/documents/{document_id}/retry")
async def retry_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Retry processing for a failed document
    """
    try:
        document_service = DocumentService()
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Retry document error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retry document")
