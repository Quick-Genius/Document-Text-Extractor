from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DocumentBase(BaseModel):
    filename: str
    originalName: str
    fileType: str
    fileSize: int
    filePath: str
    status: str

class DocumentCreate(DocumentBase):
    pass

class Job(BaseModel):
    id: str
    status: str
    class Config:
        from_attributes = True

class ProcessedData(BaseModel):
    id: str
    extractedText: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    metadata: Optional[dict] = None
    confidenceScore: Optional[float] = None
    isReviewed: bool = False
    isFinalized: bool = False
    class Config:
        from_attributes = True

class DocumentResponse(DocumentBase):
    id: str
    uploadedAt: datetime
    job: Optional[Job] = None
    processedData: Optional[ProcessedData] = None

    class Config:
        from_attributes = True

class PaginationResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    pagination: Optional[PaginationResponse] = None

class DocumentFilters(BaseModel):
    status: Optional[str] = None
    search: Optional[str] = None
    sort_by: str = "uploadedAt"
    order: str = "desc"
    page: int = 1
    limit: int = 20
