# Low-Level Design (LLD)
## Async Document Processing Workflow System

---

## 1. Detailed Component Specifications

### 1.1 Frontend Components

#### 1.1.1 File Uploader Component

**File**: `src/components/upload/FileUploader.tsx`

```typescript
interface FileUploaderProps {
  onUploadComplete: (documents: UploadedDocument[]) => void;
  maxFiles?: number;
  maxSizeBytes?: number;
}

interface UploadedDocument {
  id: string;
  filename: string;
  status: DocumentStatus;
  jobId: string;
}

interface FileUploadState {
  files: File[];
  uploadProgress: Map<string, number>;
  isUploading: boolean;
  errors: Map<string, string>;
}

// Key Features:
// - Drag and drop support via react-dropzone
// - Multiple file selection
// - File type validation (client-side)
// - File size validation
// - Preview thumbnails for images
// - Upload progress per file
// - Retry failed uploads
// - Cancel ongoing uploads

// Implementation Details:
class FileUploader {
  validateFile(file: File): ValidationResult {
    // Check file size (max 50MB)
    if (file.size > 50 * 1024 * 1024) {
      return { valid: false, error: "File too large" };
    }
    
    // Check file type
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
      'image/jpeg',
      'image/png',
      'text/csv',
      'text/html'
    ];
    
    if (!allowedTypes.includes(file.type)) {
      return { valid: false, error: "File type not supported" };
    }
    
    return { valid: true };
  }
  
  async uploadFiles(files: File[]): Promise<UploadedDocument[]> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    
    // Upload with progress tracking
    const response = await axios.post('/api/v1/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        this.updateUploadProgress(percentCompleted);
      }
    });
    
    return response.data.documents;
  }
}
```

**State Management**:
```typescript
// Using Zustand or React Context
interface UploadStore {
  uploads: Map<string, UploadState>;
  addUpload: (id: string, state: UploadState) => void;
  updateProgress: (id: string, progress: number) => void;
  completeUpload: (id: string) => void;
  failUpload: (id: string, error: string) => void;
}
```

---

#### 1.1.2 WebSocket Hook

**File**: `src/hooks/useWebSocket.ts`

```typescript
interface WebSocketMessage {
  type: 'progress' | 'job_completed' | 'job_failed' | 'pong';
  jobId: string;
  data: any;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  subscribe: (jobId: string) => void;
  unsubscribe: (jobId: string) => void;
  lastMessage: WebSocketMessage | null;
}

function useWebSocket(userId: string): UseWebSocketReturn {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const subscribedJobs = useRef<Set<string>>(new Set());
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<NodeJS.Timeout>();
  
  useEffect(() => {
    connectWebSocket();
    return () => {
      cleanup();
    };
  }, [userId]);
  
  const connectWebSocket = async () => {
    try {
      const token = await getClerkToken();
      const ws = new WebSocket(`${WS_URL}/api/v1/ws?token=${token}`);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        reconnectAttempts.current = 0;
        
        // Resubscribe to previously subscribed jobs
        subscribedJobs.current.forEach(jobId => {
          ws.send(JSON.stringify({ type: 'subscribe', jobId }));
        });
        
        // Start ping interval
        startPingInterval(ws);
      };
      
      ws.onmessage = (event) => {
        const message: WebSocketMessage = JSON.parse(event.data);
        setLastMessage(message);
        
        // Handle different message types
        switch (message.type) {
          case 'progress':
            handleProgressUpdate(message);
            break;
          case 'job_completed':
            handleJobCompleted(message);
            break;
          case 'job_failed':
            handleJobFailed(message);
            break;
          case 'pong':
            // Keepalive response
            break;
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        
        // Attempt reconnect with exponential backoff
        if (reconnectAttempts.current < 5) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          reconnectTimeout.current = setTimeout(() => {
            reconnectAttempts.current++;
            connectWebSocket();
          }, delay);
        }
      };
      
      setSocket(ws);
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
    }
  };
  
  const subscribe = (jobId: string) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'subscribe', jobId }));
      subscribedJobs.current.add(jobId);
    }
  };
  
  const unsubscribe = (jobId: string) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'unsubscribe', jobId }));
      subscribedJobs.current.delete(jobId);
    }
  };
  
  const startPingInterval = (ws: WebSocket) => {
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Ping every 30 seconds
  };
  
  const cleanup = () => {
    if (socket) {
      socket.close();
    }
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
    }
  };
  
  return { isConnected, subscribe, unsubscribe, lastMessage };
}
```

**Progress Update Handler**:
```typescript
function handleProgressUpdate(message: WebSocketMessage) {
  // Update React Query cache
  queryClient.setQueryData(['job', message.jobId], (oldData: any) => ({
    ...oldData,
    progress: message.data.progress,
    currentStep: message.data.eventType,
    message: message.data.message
  }));
  
  // Show toast notification for important events
  if (message.data.eventType === 'job_completed') {
    toast.success('Document processed successfully!');
  }
}
```

---

#### 1.1.3 Document Dashboard Component

**File**: `src/components/dashboard/DocumentList.tsx`

```typescript
interface DocumentListProps {
  initialFilters?: DocumentFilters;
}

interface DocumentFilters {
  status?: DocumentStatus[];
  search?: string;
  sortBy?: 'uploadedAt' | 'filename' | 'status';
  order?: 'asc' | 'desc';
}

interface DocumentListState {
  filters: DocumentFilters;
  selectedDocuments: Set<string>;
  viewMode: 'grid' | 'list';
}

// Key Features:
// - Real-time updates via WebSocket or React Query polling
// - Search by filename
// - Filter by status (multi-select)
// - Sort by date, filename, status
// - Bulk selection for export
// - Grid/List view toggle
// - Pagination with infinite scroll
// - Retry failed jobs
// - Delete documents

// Implementation with TanStack Table:
const columns: ColumnDef<Document>[] = [
  {
    id: 'select',
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected()}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
      />
    ),
  },
  {
    accessorKey: 'filename',
    header: 'Filename',
    cell: ({ row }) => (
      <Link to={`/documents/${row.original.id}`}>
        {row.getValue('filename')}
      </Link>
    ),
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => <StatusBadge status={row.getValue('status')} />,
  },
  {
    accessorKey: 'uploadedAt',
    header: 'Uploaded',
    cell: ({ row }) => formatDate(row.getValue('uploadedAt')),
  },
  {
    id: 'actions',
    cell: ({ row }) => <DocumentActions document={row.original} />,
  },
];

function DocumentList({ initialFilters }: DocumentListProps) {
  const [filters, setFilters] = useState<DocumentFilters>(initialFilters || {});
  const [selectedDocuments, setSelectedDocuments] = useState<Set<string>>(new Set());
  
  // Fetch documents with React Query
  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', filters],
    queryFn: () => fetchDocuments(filters),
    refetchInterval: 5000, // Polling fallback
  });
  
  // Subscribe to real-time updates via WebSocket
  const { lastMessage } = useWebSocket(userId);
  
  useEffect(() => {
    if (lastMessage?.type === 'job_completed' || lastMessage?.type === 'job_failed') {
      // Invalidate and refetch documents
      queryClient.invalidateQueries(['documents']);
    }
  }, [lastMessage]);
  
  const table = useReactTable({
    data: data?.documents || [],
    columns,
    state: { rowSelection: {} },
    // ... table configuration
  });
  
  return (
    <div>
      <DocumentFilters filters={filters} onChange={setFilters} />
      <DataTable table={table} />
      <Pagination {...data?.pagination} />
    </div>
  );
}
```

**Status Badge Component**:
```typescript
function StatusBadge({ status }: { status: DocumentStatus }) {
  const statusConfig = {
    PENDING: { color: 'gray', icon: ClockIcon, label: 'Pending' },
    QUEUED: { color: 'blue', icon: ListIcon, label: 'Queued' },
    PROCESSING: { color: 'yellow', icon: SpinnerIcon, label: 'Processing' },
    COMPLETED: { color: 'green', icon: CheckIcon, label: 'Completed' },
    FAILED: { color: 'red', icon: XIcon, label: 'Failed' },
    CANCELLED: { color: 'gray', icon: BanIcon, label: 'Cancelled' },
  };
  
  const config = statusConfig[status];
  
  return (
    <Badge variant={config.color}>
      <config.icon className="w-3 h-3 mr-1" />
      {config.label}
    </Badge>
  );
}
```

---

#### 1.1.4 Document Detail & Edit Component

**File**: `src/components/detail/DocumentDetail.tsx`

```typescript
interface DocumentDetailProps {
  documentId: string;
}

interface ProcessedDataFormValues {
  title: string;
  category: string;
  summary: string;
  keywords: string[];
}

function DocumentDetail({ documentId }: DocumentDetailProps) {
  const { data: document, isLoading } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => fetchDocumentById(documentId),
  });
  
  const { mutate: updateProcessedData } = useMutation({
    mutationFn: (data: ProcessedDataFormValues) => 
      updateDocumentProcessedData(documentId, data),
    onSuccess: () => {
      toast.success('Changes saved successfully');
      queryClient.invalidateQueries(['document', documentId]);
    },
  });
  
  const { mutate: finalizeDocument } = useMutation({
    mutationFn: () => finalizeDocumentData(documentId),
    onSuccess: () => {
      toast.success('Document finalized');
      queryClient.invalidateQueries(['document', documentId]);
    },
  });
  
  if (isLoading) return <LoadingSpinner />;
  if (!document) return <NotFound />;
  
  return (
    <div className="grid grid-cols-12 gap-6">
      {/* Left: Document Info & Preview */}
      <div className="col-span-4">
        <DocumentInfo document={document} />
        <DocumentPreview document={document} />
      </div>
      
      {/* Right: Processed Data & Edit Form */}
      <div className="col-span-8">
        {document.job && (
          <JobProgressCard job={document.job} />
        )}
        
        {document.processedData && (
          <ProcessedDataEditor
            data={document.processedData}
            onSave={updateProcessedData}
            onFinalize={finalizeDocument}
          />
        )}
      </div>
    </div>
  );
}
```

**Processed Data Editor**:
```typescript
function ProcessedDataEditor({ data, onSave, onFinalize }: EditorProps) {
  const form = useForm<ProcessedDataFormValues>({
    resolver: zodResolver(processedDataSchema),
    defaultValues: {
      title: data.title || '',
      category: data.category || '',
      summary: data.summary || '',
      keywords: data.keywords || [],
    },
  });
  
  const [isEditing, setIsEditing] = useState(false);
  
  const handleSave = (values: ProcessedDataFormValues) => {
    onSave(values);
    setIsEditing(false);
  };
  
  const handleFinalize = () => {
    if (confirm('Are you sure? Finalized documents cannot be edited.')) {
      onFinalize();
    }
  };
  
  if (data.isFinalized) {
    return <ReadOnlyView data={data} />;
  }
  
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSave)}>
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input {...field} disabled={!isEditing} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        
        {/* Similar fields for category, summary, keywords */}
        
        <div className="flex gap-2">
          {!isEditing ? (
            <>
              <Button onClick={() => setIsEditing(true)}>Edit</Button>
              <Button variant="secondary" onClick={handleFinalize}>
                Finalize
              </Button>
            </>
          ) : (
            <>
              <Button type="submit">Save</Button>
              <Button variant="outline" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
            </>
          )}
        </div>
      </form>
    </Form>
  );
}
```

---

### 1.2 Backend Implementation

#### 1.2.1 FastAPI Application Setup

**File**: `backend/app/main.py`

```python
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from app.api.v1 import documents, jobs, export, websocket
from app.core.config import settings
from app.core.websocket_manager import websocket_manager
from app.utils.redis_client import redis_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting application...")
    await redis_client.connect()
    await websocket_manager.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await websocket_manager.stop()
    await redis_client.disconnect()

# Create FastAPI app
app = FastAPI(
    title="Document Processing API",
    version="1.0.0",
    description="Async document processing workflow system",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/health/deep")
async def deep_health_check():
    """Check all dependencies"""
    checks = {
        "redis": await redis_client.ping(),
        "database": await check_database_connection(),
        "celery": await check_celery_workers(),
    }
    
    is_healthy = all(checks.values())
    status_code = 200 if is_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if is_healthy else "unhealthy", "checks": checks}
    )

# Include routers
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
```

**Configuration**: `backend/app/config.py`

```python
from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # Application
    DEBUG: bool = False
    APP_NAME: str = "Document Processing API"
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Database (Neon DB)
    DATABASE_URL: str
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    
    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # Clerk Authentication
    CLERK_SECRET_KEY: str
    CLERK_FRONTEND_API: str
    
    # File Storage
    STORAGE_TYPE: str = "local"  # "local" or "s3"
    LOCAL_STORAGE_PATH: str = "/app/storage"
    
    # AWS S3 (if STORAGE_TYPE = "s3")
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_S3_BUCKET: str | None = None
    AWS_REGION: str = "us-east-1"
    
    # File Upload Limits
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_FILES_PER_UPLOAD: int = 10
    
    # Processing
    TASK_TIMEOUT: int = 1800  # 30 minutes
    MAX_RETRIES: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

---

#### 1.2.2 Authentication Middleware

**File**: `backend/app/core/auth.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from clerk_backend_api import Clerk
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()
clerk_client = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validate Clerk JWT token and return user information
    """
    try:
        token = credentials.credentials
        
        # Verify JWT with Clerk
        session = clerk_client.sessions.verify_token(token)
        
        if not session or not session.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        
        # Get user details from Clerk
        user = clerk_client.users.get(session.user_id)
        
        return {
            "id": user.id,
            "email": user.email_addresses[0].email_address if user.email_addresses else None,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

async def get_current_user_id(
    user: dict = Depends(get_current_user)
) -> str:
    """Extract user ID from authenticated user"""
    return user["id"]
```

**Database User Sync**:
```python
from app.models import User
from prisma import Prisma

async def sync_user_from_clerk(clerk_user: dict) -> User:
    """
    Sync user from Clerk to local database
    Creates or updates user record
    """
    db = Prisma()
    await db.connect()
    
    user = await db.user.upsert(
        where={"clerkId": clerk_user["id"]},
        data={
            "create": {
                "clerkId": clerk_user["id"],
                "email": clerk_user["email"],
                "firstName": clerk_user["first_name"],
                "lastName": clerk_user["last_name"],
            },
            "update": {
                "email": clerk_user["email"],
                "firstName": clerk_user["first_name"],
                "lastName": clerk_user["last_name"],
            },
        },
    )
    
    await db.disconnect()
    return user
```

---

#### 1.2.3 Document Upload Endpoint

**File**: `backend/app/api/v1/documents.py`

```python
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Form
from typing import List, Optional
from app.core.auth import get_current_user_id
from app.services.document_service import DocumentService
from app.schemas.document import DocumentResponse, DocumentListResponse, DocumentFilters
from app.utils.exceptions import StorageError, ValidationError
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

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
```

---

#### 1.2.4 Document Service Layer

**File**: `backend/app/services/document_service.py`

```python
from typing import List, Optional
from fastapi import UploadFile
from prisma import Prisma
from app.schemas.document import DocumentResponse, DocumentListResponse, DocumentFilters, PaginationResponse
from app.services.storage_service import StorageService
from app.workers.tasks import process_document_task
from app.utils.exceptions import NotFoundError, PermissionError
import uuid
import logging

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self):
        self.db = Prisma()
        self.storage = StorageService()
    
    async def create_documents_from_upload(
        self,
        user_id: str,
        files: List[UploadFile],
        category: Optional[str] = None
    ) -> List[DocumentResponse]:
        """
        Process file uploads and create document records
        """
        await self.db.connect()
        
        try:
            documents = []
            
            for file in files:
                # Generate unique filename
                file_id = str(uuid.uuid4())
                file_ext = file.filename.split('.')[-1] if '.' in file.filename else ''
                stored_filename = f"{file_id}.{file_ext}" if file_ext else file_id
                
                # Save file to storage
                file_path = await self.storage.save_file(
                    file=file,
                    filename=stored_filename,
                    folder="uploads"
                )
                
                # Create document record
                document = await self.db.document.create(
                    data={
                        "userId": user_id,
                        "filename": stored_filename,
                        "originalName": file.filename,
                        "fileType": file.content_type,
                        "fileSize": file.size,
                        "filePath": file_path,
                        "status": "QUEUED",
                    }
                )
                
                # Create job record
                celery_task_id = str(uuid.uuid4())
                job = await self.db.job.create(
                    data={
                        "documentId": document.id,
                        "celeryTaskId": celery_task_id,
                        "status": "QUEUED",
                    }
                )
                
                # Dispatch Celery task
                process_document_task.apply_async(
                    args=[document.id, file_path],
                    task_id=celery_task_id,
                    countdown=2  # Slight delay to ensure DB commit
                )
                
                logger.info(f"Dispatched processing task {celery_task_id} for document {document.id}")
                
                documents.append(DocumentResponse(
                    **document.dict(),
                    job=job.dict()
                ))
            
            return documents
            
        finally:
            await self.db.disconnect()
    
    async def list_documents(
        self,
        user_id: str,
        filters: DocumentFilters
    ) -> DocumentListResponse:
        """
        List user's documents with filtering, sorting, and pagination
        """
        await self.db.connect()
        
        try:
            # Build where clause
            where = {"userId": user_id}
            
            if filters.status:
                where["status"] = filters.status
            
            if filters.search:
                where["originalName"] = {"contains": filters.search, "mode": "insensitive"}
            
            # Calculate pagination
            skip = (filters.page - 1) * filters.limit
            
            # Query documents
            documents = await self.db.document.find_many(
                where=where,
                skip=skip,
                take=filters.limit,
                order_by={filters.sort_by: filters.order},
                include={"job": True, "processedData": True}
            )
            
            # Get total count
            total = await self.db.document.count(where=where)
            
            pagination = PaginationResponse(
                total=total,
                page=filters.page,
                limit=filters.limit,
                pages=(total + filters.limit - 1) // filters.limit
            )
            
            return DocumentListResponse(
                documents=documents,
                pagination=pagination
            )
            
        finally:
            await self.db.disconnect()
    
    async def get_document_by_id(
        self,
        document_id: str,
        user_id: str
    ) -> DocumentResponse:
        """
        Get document by ID with authorization check
        """
        await self.db.connect()
        
        try:
            document = await self.db.document.find_unique(
                where={"id": document_id},
                include={"job": True, "processedData": True}
            )
            
            if not document:
                raise NotFoundError("Document not found")
            
            if document.userId != user_id:
                raise PermissionError("Unauthorized access")
            
            return DocumentResponse(**document.dict())
            
        finally:
            await self.db.disconnect()
    
    async def update_processed_data(
        self,
        document_id: str,
        user_id: str,
        data: dict
    ):
        """
        Update processed data for a document
        """
        await self.db.connect()
        
        try:
            # Verify ownership
            document = await self.db.document.find_unique(
                where={"id": document_id},
                include={"processedData": True}
            )
            
            if not document or document.userId != user_id:
                raise NotFoundError("Document not found")
            
            if document.processedData and document.processedData.isFinalized:
                raise PermissionError("Cannot edit finalized document")
            
            # Update or create processed data
            processed_data = await self.db.processeddata.upsert(
                where={"documentId": document_id},
                data={
                    "create": {
                        "documentId": document_id,
                        "title": data.get("title"),
                        "category": data.get("category"),
                        "summary": data.get("summary"),
                        "keywords": data.get("keywords", []),
                        "isReviewed": True,
                    },
                    "update": {
                        "title": data.get("title"),
                        "category": data.get("category"),
                        "summary": data.get("summary"),
                        "keywords": data.get("keywords", []),
                        "isReviewed": True,
                        "reviewedAt": "now()",
                    },
                },
            )
            
            return processed_data
            
        finally:
            await self.db.disconnect()
    
    async def finalize_document(
        self,
        document_id: str,
        user_id: str
    ):
        """
        Finalize a document (lock from further edits)
        """
        await self.db.connect()
        
        try:
            # Verify ownership
            document = await self.db.document.find_unique(
                where={"id": document_id},
                include={"processedData": True}
            )
            
            if not document or document.userId != user_id:
                raise NotFoundError("Document not found")
            
            if not document.processedData:
                raise ValidationError("Cannot finalize document without processed data")
            
            if document.processedData.isFinalized:
                raise ValidationError("Document already finalized")
            
            # Update processed data
            processed_data = await self.db.processeddata.update(
                where={"documentId": document_id},
                data={
                    "isFinalized": True,
                    "finalizedAt": "now()",
                },
            )
            
            return processed_data
            
        finally:
            await self.db.disconnect()
    
    async def delete_document(
        self,
        document_id: str,
        user_id: str
    ):
        """
        Delete a document and its associated data
        """
        await self.db.connect()
        
        try:
            # Verify ownership
            document = await self.db.document.find_unique(
                where={"id": document_id}
            )
            
            if not document or document.userId != user_id:
                raise NotFoundError("Document not found")
            
            # Cancel job if still processing
            if document.job and document.job.status in ["QUEUED", "PROCESSING"]:
                await self.cancel_job(document.job.id)
            
            # Delete file from storage
            await self.storage.delete_file(document.filePath)
            
            # Delete database record (cascade will handle related records)
            await self.db.document.delete(where={"id": document_id})
            
            logger.info(f"Deleted document {document_id}")
            
        finally:
            await self.db.disconnect()
```

---

#### 1.2.5 Celery Worker Configuration

**File**: `backend/app/workers/celery_app.py`

```python
from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "document_processor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"]
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
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

# Task routes
celery_app.conf.task_routes = {
    "app.workers.tasks.process_document_task": {"queue": "default"},
}

# Celery events
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks if needed"""
    pass

logger.info("Celery app configured successfully")
```

---

#### 1.2.6 Document Processing Task

**File**: `backend/app/workers/tasks.py`

```python
from celery import Task
from app.workers.celery_app import celery_app
from app.workers.processors.pdf_processor import PDFProcessor
from app.workers.processors.docx_processor import DOCXProcessor
from app.workers.processors.image_processor import ImageProcessor
from app.workers.processors.text_processor import TextProcessor
from prisma import Prisma
from app.utils.redis_client import redis_client
import logging
import asyncio
import time

logger = logging.getLogger(__name__)

class CallbackTask(Task):
    """Base task with callbacks for lifecycle events"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Task {task_id} failed: {exc}")
        asyncio.run(self.mark_job_failed(args[0], str(exc)))
    
    async def mark_job_failed(self, document_id: str, error: str):
        """Mark job as failed in database"""
        db = Prisma()
        await db.connect()
        
        try:
            # Get job
            document = await db.document.find_unique(
                where={"id": document_id},
                include={"job": True}
            )
            
            if document and document.job:
                # Update job status
                await db.job.update(
                    where={"id": document.job.id},
                    data={
                        "status": "FAILED",
                        "errorMessage": error,
                        "failedAt": "now()",
                    },
                )
                
                # Update document status
                await db.document.update(
                    where={"id": document_id},
                    data={"status": "FAILED"},
                )
                
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
    Async document processing workflow
    """
    db = Prisma()
    await db.connect()
    
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
        await publish_progress(job_id, "job_started", "Starting document processing", 0)
        await update_job_status(db, job_id, "PROCESSING", started=True)
        await update_document_status(db, document_id, "PROCESSING")
        
        # Stage 2: Parsing Started
        await publish_progress(job_id, "parsing_started", "Parsing document", 10)
        
        # Determine file type and select processor
        processor = get_processor_for_file(document.fileType)
        
        # Parse document
        parsed_data = await processor.parse(file_path)
        
        # Check cancellation
        if await check_cancellation(job_id):
            await mark_job_cancelled(db, job_id, document_id)
            return {"status": "cancelled"}
        
        # Stage 3: Parsing Completed
        await publish_progress(job_id, "parsing_completed", "Document parsed successfully", 40)
        
        # Stage 4: Extraction Started
        await publish_progress(job_id, "extraction_started", "Extracting structured fields", 50)
        
        # Extract structured data
        extracted_data = await processor.extract_structured_data(parsed_data)
        
        # Check cancellation
        if await check_cancellation(job_id):
            await mark_job_cancelled(db, job_id, document_id)
            return {"status": "cancelled"}
        
        # Stage 5: Extraction Completed
        await publish_progress(job_id, "extraction_completed", "Extraction complete", 90)
        
        # Stage 6: Store Results
        await publish_progress(job_id, "storing_results", "Saving processed data", 95)
        
        # Create ProcessedData record
        processed_data = await db.processeddata.create(
            data={
                "documentId": document_id,
                "extractedText": extracted_data.get("text", ""),
                "title": extracted_data.get("title"),
                "category": extracted_data.get("category"),
                "summary": extracted_data.get("summary"),
                "keywords": extracted_data.get("keywords", []),
                "metadata": extracted_data.get("metadata", {}),
            }
        )
        
        # Stage 7: Job Completed
        await publish_progress(job_id, "job_completed", "Processing completed successfully", 100)
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
        await publish_progress(job_id, "job_failed", f"Processing failed: {str(e)}", 0)
        raise
        
    finally:
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

async def mark_job_cancelled(db: Prisma, job_id: str, document_id: str):
    """Mark job and document as cancelled"""
    await db.job.update(
        where={"id": job_id},
        data={"status": "CANCELLED"},
    )
    await db.document.update(
        where={"id": document_id},
        data={"status": "CANCELLED"},
    )
    await publish_progress(job_id, "job_cancelled", "Job was cancelled by user", 0)

async def publish_progress(job_id: str, event_type: str, message: str, progress: int):
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
        {
            "status": event_type,
            "message": message,
            "progress": str(progress),
            "updated_at": str(time.time())
        }
    )
    await redis_client.expire(f"job:progress:{job_id}", 3600)  # 1 hour TTL
    
    # Store in database
    db = Prisma()
    await db.connect()
    try:
        await db.progressevent.create(
            data={
                "jobId": job_id,
                "eventType": event_type,
                "message": message,
                "progress": progress,
            }
        )
    finally:
        await db.disconnect()

async def update_job_status(db: Prisma, job_id: str, status: str, started: bool = False, completed: bool = False):
    """Update job status in database"""
    update_data = {"status": status}
    
    if started:
        update_data["startedAt"] = "now()"
    if completed:
        update_data["completedAt"] = "now()"
    
    await db.job.update(
        where={"id": job_id},
        data=update_data,
    )

async def update_document_status(db: Prisma, document_id: str, status: str):
    """Update document status in database"""
    await db.document.update(
        where={"id": document_id},
        data={"status": status},
    )
```

---

#### 1.2.7 PDF Processor

**File**: `backend/app/workers/processors/pdf_processor.py`

```python
import PyPDF2
import pytesseract
from PIL import Image
import io
import re
from typing import Dict, Any
from app.workers.processors.base_processor import BaseProcessor
import logging

logger = logging.getLogger(__name__)

class PDFProcessor(BaseProcessor):
    """Processor for PDF documents"""
    
    async def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse PDF file and extract text
        
        Returns:
            {
                "text": "extracted text content",
                "metadata": {
                    "pages": 10,
                    "has_images": True,
                    ...
                }
            }
        """
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Extract metadata
                metadata = {
                    "pages": len(pdf_reader.pages),
                    "has_images": False,
                }
                
                # Extract text from all pages
                text_parts = []
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text_parts.append(page_text)
                    
                    # Check for images (simple heuristic)
                    if '/XObject' in page['/Resources']:
                        metadata["has_images"] = True
                
                full_text = "\n\n".join(text_parts)
                
                # If text extraction failed (image-based PDF), try OCR
                if len(full_text.strip()) < 100:
                    logger.info(f"Text extraction yielded little content, attempting OCR")
                    full_text = await self.ocr_pdf(file_path)
                    metadata["ocr_used"] = True
                
                return {
                    "text": full_text,
                    "metadata": metadata
                }
                
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            raise
    
    async def ocr_pdf(self, file_path: str) -> str:
        """
        Perform OCR on image-based PDF
        """
        # This is a simplified implementation
        # In production, you might use pdf2image + pytesseract
        try:
            import pdf2image
            
            images = pdf2image.convert_from_path(file_path)
            text_parts = []
            
            for image in images:
                text = pytesseract.image_to_string(image)
                text_parts.append(text)
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""
    
    async def extract_structured_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured fields from parsed PDF
        """
        text = parsed_data["text"]
        
        # Title extraction (first non-empty line or first 100 chars)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        title = lines[0] if lines else text[:100]
        
        # Category detection (simple keyword matching)
        category = self.detect_category(text)
        
        # Summary generation (first paragraph or first 500 chars)
        summary = self.extract_summary(text)
        
        # Keyword extraction
        keywords = self.extract_keywords(text)
        
        return {
            "text": text,
            "title": title,
            "category": category,
            "summary": summary,
            "keywords": keywords,
            "metadata": parsed_data["metadata"]
        }
    
    def detect_category(self, text: str) -> str:
        """Detect document category based on keywords"""
        text_lower = text.lower()
        
        category_keywords = {
            "invoice": ["invoice", "bill", "payment due", "total amount"],
            "contract": ["agreement", "contract", "party", "terms and conditions"],
            "report": ["report", "analysis", "findings", "conclusion"],
            "resume": ["resume", "cv", "experience", "education", "skills"],
            "letter": ["dear", "sincerely", "regards", "letter"],
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return category
        
        return "document"
    
    def extract_summary(self, text: str, max_length: int = 500) -> str:
        """Extract first meaningful paragraph as summary"""
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        
        if paragraphs:
            summary = paragraphs[0]
        else:
            summary = text
        
        # Truncate to max length
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(' ', 1)[0] + "..."
        
        return summary
    
    def extract_keywords(self, text: str, max_keywords: int = 10) -> list:
        """Extract keywords using simple frequency analysis"""
        # Remove common words (stopwords)
        stopwords = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
                        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                        'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'])
        
        # Tokenize and clean
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        words = [w for w in words if w not in stopwords]
        
        # Count frequency
        from collections import Counter
        word_freq = Counter(words)
        
        # Get top keywords
        keywords = [word for word, _ in word_freq.most_common(max_keywords)]
        
        return keywords
```

**Base Processor**: `backend/app/workers/processors/base_processor.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseProcessor(ABC):
    """Base class for document processors"""
    
    @abstractmethod
    async def parse(self, file_path: str) -> Dict[str, Any]:
        """Parse file and extract raw content"""
        pass
    
    @abstractmethod
    async def extract_structured_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured fields from parsed content"""
        pass
```

---

#### 1.2.8 WebSocket Manager

**File**: `backend/app/core/websocket_manager.py`

```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
from app.utils.redis_client import redis_client
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manage WebSocket connections and broadcast progress updates"""
    
    def __init__(self):
        # user_id -> set of WebSocket connections
        self.connections: Dict[str, Set[WebSocket]] = {}
        
        # job_id -> set of user_ids subscribed
        self.job_subscriptions: Dict[str, Set[str]] = {}
        
        # Background task for Redis Pub/Sub
        self.pubsub_task: asyncio.Task = None
        self.running = False
    
    async def start(self):
        """Start the WebSocket manager and Redis listener"""
        self.running = True
        self.pubsub_task = asyncio.create_task(self.listen_to_redis())
        logger.info("WebSocket manager started")
    
    async def stop(self):
        """Stop the WebSocket manager"""
        self.running = False
        if self.pubsub_task:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass
        logger.info("WebSocket manager stopped")
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Register a new WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.connections:
            self.connections[user_id] = set()
        
        self.connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected, total connections: {len(self.connections[user_id])}")
    
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Unregister a WebSocket connection"""
        if user_id in self.connections:
            self.connections[user_id].discard(websocket)
            
            if not self.connections[user_id]:
                del self.connections[user_id]
                
                # Clean up subscriptions
                for job_id, subscribers in list(self.job_subscriptions.items()):
                    subscribers.discard(user_id)
                    if not subscribers:
                        del self.job_subscriptions[job_id]
        
        logger.info(f"User {user_id} disconnected")
    
    async def subscribe(self, user_id: str, job_id: str):
        """Subscribe a user to job updates"""
        if job_id not in self.job_subscriptions:
            self.job_subscriptions[job_id] = set()
        
        self.job_subscriptions[job_id].add(user_id)
        logger.info(f"User {user_id} subscribed to job {job_id}")
        
        # Send current job status immediately
        await self.send_current_status(user_id, job_id)
    
    async def unsubscribe(self, user_id: str, job_id: str):
        """Unsubscribe a user from job updates"""
        if job_id in self.job_subscriptions:
            self.job_subscriptions[job_id].discard(user_id)
            
            if not self.job_subscriptions[job_id]:
                del self.job_subscriptions[job_id]
        
        logger.info(f"User {user_id} unsubscribed from job {job_id}")
    
    async def send_current_status(self, user_id: str, job_id: str):
        """Send current job status from Redis cache"""
        try:
            progress_data = await redis_client.hgetall(f"job:progress:{job_id}")
            
            if progress_data:
                message = {
                    "type": "progress",
                    "jobId": job_id,
                    "data": {
                        "status": progress_data.get("status", "unknown"),
                        "message": progress_data.get("message", ""),
                        "progress": int(progress_data.get("progress", 0)),
                        "timestamp": float(progress_data.get("updated_at", 0)),
                    }
                }
                
                await self.send_to_user(user_id, message)
        except Exception as e:
            logger.error(f"Error sending current status: {e}")
    
    async def listen_to_redis(self):
        """Listen to Redis Pub/Sub for progress updates"""
        pubsub = await redis_client.subscribe("progress:*")
        
        try:
            while self.running:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                
                if message and message["type"] == "message":
                    await self.handle_redis_message(message)
                
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Redis listener cancelled")
        except Exception as e:
            logger.error(f"Error in Redis listener: {e}")
        finally:
            await pubsub.close()
    
    async def handle_redis_message(self, message: dict):
        """Handle incoming Redis Pub/Sub message"""
        try:
            channel = message["channel"].decode()
            data = json.loads(message["data"])
            
            # Extract job_id from channel (format: progress:{job_id})
            job_id = channel.split(":", 1)[1]
            
            # Broadcast to subscribed users
            if job_id in self.job_subscriptions:
                for user_id in self.job_subscriptions[job_id]:
                    await self.send_to_user(user_id, data)
        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to all connections for a user"""
        if user_id not in self.connections:
            return
        
        disconnected = []
        
        for websocket in self.connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected sockets
        for websocket in disconnected:
            await self.disconnect(websocket, user_id)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected users"""
        for user_id in list(self.connections.keys()):
            await self.send_to_user(user_id, message)

# Global instance
websocket_manager = WebSocketManager()
```

**WebSocket Endpoint**: `backend/app/api/v1/websocket.py`

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from app.core.auth import get_current_user_id
from app.core.websocket_manager import websocket_manager
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket endpoint for real-time progress updates
    
    Query params:
        token: Clerk JWT token for authentication
    """
    try:
        # Authenticate user
        # Note: In production, validate JWT properly
        user_id = await validate_ws_token(token)
        
        if not user_id:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        
        # Connect
        await websocket_manager.connect(websocket, user_id)
        
        try:
            # Handle incoming messages
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                message_type = message.get("type")
                
                if message_type == "subscribe":
                    job_id = message.get("jobId")
                    if job_id:
                        await websocket_manager.subscribe(user_id, job_id)
                
                elif message_type == "unsubscribe":
                    job_id = message.get("jobId")
                    if job_id:
                        await websocket_manager.unsubscribe(user_id, job_id)
                
                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for user {user_id}")
        finally:
            await websocket_manager.disconnect(websocket, user_id)
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass

async def validate_ws_token(token: str) -> str:
    """Validate WebSocket token and return user_id"""
    try:
        from clerk_backend_api import Clerk
        from app.core.config import settings
        
        clerk_client = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)
        session = clerk_client.sessions.verify_token(token)
        
        if session and session.user_id:
            return session.user_id
        
        return None
        
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None
```

---

## 2. Testing Strategy

### 2.1 Unit Tests Structure

**File**: `backend/tests/unit/test_services/test_document_service.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.document_service import DocumentService
from app.schemas.document import DocumentFilters

@pytest.fixture
def mock_db():
    """Mock Prisma database"""
    db = AsyncMock()
    db.connect = AsyncMock()
    db.disconnect = AsyncMock()
    db.document = AsyncMock()
    db.job = AsyncMock()
    return db

@pytest.fixture
def mock_storage():
    """Mock storage service"""
    storage = AsyncMock()
    storage.save_file = AsyncMock(return_value="/path/to/file")
    return storage

@pytest.fixture
def document_service(mock_db, mock_storage):
    """Create document service with mocked dependencies"""
    service = DocumentService()
    service.db = mock_db
    service.storage = mock_storage
    return service

@pytest.mark.asyncio
async def test_create_documents_from_upload(document_service, mock_db):
    """Test document creation from file upload"""
    # Arrange
    user_id = "user-123"
    mock_file = Mock()
    mock_file.filename = "test.pdf"
    mock_file.content_type = "application/pdf"
    mock_file.size = 1024
    
    mock_db.document.create.return_value = Mock(
        id="doc-123",
        userId=user_id,
        filename="test.pdf",
        status="QUEUED"
    )
    
    mock_db.job.create.return_value = Mock(
        id="job-123",
        documentId="doc-123",
        status="QUEUED"
    )
    
    # Act
    with patch('app.workers.tasks.process_document_task.apply_async'):
        documents = await document_service.create_documents_from_upload(
            user_id=user_id,
            files=[mock_file],
            category="invoice"
        )
    
    # Assert
    assert len(documents) == 1
    assert documents[0].id == "doc-123"
    mock_db.document.create.assert_called_once()
    mock_db.job.create.assert_called_once()

@pytest.mark.asyncio
async def test_list_documents_with_filters(document_service, mock_db):
    """Test document listing with filters"""
    # Arrange
    user_id = "user-123"
    filters = DocumentFilters(
        status="COMPLETED",
        search="invoice",
        page=1,
        limit=20
    )
    
    mock_db.document.find_many.return_value = [
        Mock(id="doc-1", filename="invoice1.pdf"),
        Mock(id="doc-2", filename="invoice2.pdf"),
    ]
    mock_db.document.count.return_value = 2
    
    # Act
    result = await document_service.list_documents(user_id, filters)
    
    # Assert
    assert len(result.documents) == 2
    assert result.pagination.total == 2
    mock_db.document.find_many.assert_called_once()

# More tests...
```

**File**: `backend/tests/unit/test_processors/test_pdf_processor.py`

```python
import pytest
from app.workers.processors.pdf_processor import PDFProcessor
import tempfile
import os

@pytest.fixture
def pdf_processor():
    return PDFProcessor()

@pytest.fixture
def sample_pdf():
    """Create a temporary PDF file for testing"""
    # Create a simple PDF using reportlab
    from reportlab.pdfgen import canvas
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        pdf_path = f.name
        c = canvas.Canvas(pdf_path)
        c.drawString(100, 750, "Test Document")
        c.drawString(100, 730, "This is a sample invoice for testing.")
        c.save()
    
    yield pdf_path
    
    # Cleanup
    os.unlink(pdf_path)

@pytest.mark.asyncio
async def test_parse_pdf(pdf_processor, sample_pdf):
    """Test PDF parsing"""
    # Act
    result = await pdf_processor.parse(sample_pdf)
    
    # Assert
    assert "text" in result
    assert "metadata" in result
    assert len(result["text"]) > 0
    assert result["metadata"]["pages"] > 0

@pytest.mark.asyncio
async def test_extract_structured_data(pdf_processor):
    """Test structured data extraction"""
    # Arrange
    parsed_data = {
        "text": "Invoice #12345\nTotal Amount: $100.00\nPayment due: 2024-01-01",
        "metadata": {"pages": 1}
    }
    
    # Act
    result = await pdf_processor.extract_structured_data(parsed_data)
    
    # Assert
    assert result["category"] == "invoice"
    assert len(result["keywords"]) > 0
    assert result["title"] is not None

# More tests...
```

### 2.2 Test Fixtures

**File**: `backend/tests/conftest.py`

```python
import pytest
import asyncio
from prisma import Prisma

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db():
    """Create test database connection"""
    client = Prisma()
    await client.connect()
    yield client
    await client.disconnect()

@pytest.fixture
def mock_celery_task():
    """Mock Celery task execution"""
    with patch('app.workers.tasks.process_document_task.apply_async') as mock:
        yield mock

# More fixtures...
```

---

## 3. Docker Compose Configuration

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  # PostgreSQL Database (can be replaced with Neon DB connection)
  postgres:
    image: postgres:15-alpine
    container_name: docproc_postgres
    environment:
      POSTGRES_USER: docproc
      POSTGRES_PASSWORD: docproc_password
      POSTGRES_DB: docproc_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - docproc_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U docproc"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis
  redis:
    image: redis:7-alpine
    container_name: docproc_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - docproc_network
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # FastAPI Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: docproc_backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://docproc:docproc_password@postgres:5432/docproc_db
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - CLERK_SECRET_KEY=${CLERK_SECRET_KEY}
      - CLERK_FRONTEND_API=${CLERK_FRONTEND_API}
      - STORAGE_TYPE=local
      - LOCAL_STORAGE_PATH=/app/storage
    volumes:
      - ./backend:/app
      - storage_data:/app/storage
    networks:
      - docproc_network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Celery Worker
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: docproc_worker
    environment:
      - DATABASE_URL=postgresql://docproc:docproc_password@postgres:5432/docproc_db
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - STORAGE_TYPE=local
      - LOCAL_STORAGE_PATH=/app/storage
    volumes:
      - ./backend:/app
      - storage_data:/app/storage
    networks:
      - docproc_network
    depends_on:
      - postgres
      - redis
    command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=4

  # Flower (Celery Monitoring)
  flower:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: docproc_flower
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    networks:
      - docproc_network
    depends_on:
      - redis
      - worker
    command: celery -A app.workers.celery_app flower --port=5555

  # React Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: docproc_frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_WS_URL=ws://localhost:8000
      - VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}
    volumes:
      - ./frontend:/app
      - /app/node_modules
    networks:
      - docproc_network
    depends_on:
      - backend
    command: npm run dev -- --host 0.0.0.0

volumes:
  postgres_data:
  redis_data:
  storage_data:

networks:
  docproc_network:
    driver: bridge
```

**Backend Dockerfile**: `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Generate Prisma client
RUN prisma generate

# Create storage directory
RUN mkdir -p /app/storage/uploads /app/storage/processed

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile**: `frontend/Dockerfile`

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

---

## 4. Environment Configuration

**`.env.example`**:

```env
# Database (Neon DB or local PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/docproc_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Clerk Authentication
CLERK_SECRET_KEY=your_clerk_secret_key
CLERK_FRONTEND_API=your_clerk_frontend_api
VITE_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key

# File Storage
STORAGE_TYPE=local  # or "s3"
LOCAL_STORAGE_PATH=/app/storage

# AWS S3 (if STORAGE_TYPE=s3)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_REGION=us-east-1

# Application
DEBUG=true
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

---

## 5. Idempotency Implementation

### 5.1 Idempotent Task Execution

```python
# In tasks.py

@celery_app.task(bind=True, base=CallbackTask, name="app.workers.tasks.process_document_task")
def process_document_task(self, document_id: str, file_path: str):
    """Idempotent document processing task"""
    return asyncio.run(process_document_idempotent(self, document_id, file_path))

async def process_document_idempotent(task: Task, document_id: str, file_path: str):
    """
    Idempotent wrapper for document processing
    
    Ensures:
    1. Same task doesn't run concurrently
    2. On retry, previous partial results are cleaned up
    3. Task can be safely retried without side effects
    """
    db = Prisma()
    await db.connect()
    
    try:
        # Get job
        document = await db.document.find_unique(
            where={"id": document_id},
            include={"job": True, "processedData": True}
        )
        
        if not document or not document.job:
            raise Exception("Document or job not found")
        
        job = document.job
        
        # Check if already completed
        if job.status == "COMPLETED":
            logger.info(f"Job {job.id} already completed, skipping")
            return {"status": "already_completed"}
        
        # Check if currently processing by another worker
        if job.status == "PROCESSING":
            # Verify the task is actually running
            task_result = AsyncResult(job.celeryTaskId, app=celery_app)
            if task_result.state in ["PENDING", "STARTED", "RETRY"]:
                logger.info(f"Job {job.id} is being processed by another worker")
                raise Ignore()  # Celery will not retry
        
        # Clean up any partial results from previous failed attempts
        if document.processedData:
            await db.processeddata.delete(where={"documentId": document_id})
            logger.info(f"Cleaned up partial results for document {document_id}")
        
        # Proceed with processing
        return await process_document_async(task, document_id, file_path)
        
    finally:
        await db.disconnect()
```

### 5.2 Idempotent Retry Strategy

```python
# Retry with exponential backoff
@celery_app.task(
    bind=True,
    base=CallbackTask,
    autoretry_for=(DatabaseError, NetworkError),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def process_document_task_with_retry(self, document_id: str, file_path: str):
    """Task with automatic retry on specific errors"""
    return asyncio.run(process_document_idempotent(self, document_id, file_path))
```

---

## 6. Cancellation Support

### 6.1 Backend Implementation

**Job Cancellation Endpoint**:

```python
# In jobs.py

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Cancel a running job"""
    try:
        # Verify ownership
        db = Prisma()
        await db.connect()
        
        job = await db.job.find_unique(
            where={"id": job_id},
            include={"document": True}
        )
        
        if not job or job.document.userId != user_id:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status not in ["QUEUED", "PROCESSING"]:
            raise HTTPException(status_code=400, detail="Job cannot be cancelled")
        
        # Set cancellation flag in Redis
        await redis_client.set(f"job:cancel:{job_id}", "1", ex=3600)
        
        # Revoke Celery task
        celery_app.control.revoke(job.celeryTaskId, terminate=True)
        
        # Update job status
        await db.job.update(
            where={"id": job_id},
            data={"status": "CANCELLED"},
        )
        
        await db.document.update(
            where={"id": job.document.id},
            data={"status": "CANCELLED"},
        )
        
        await db.disconnect()
        
        logger.info(f"Cancelled job {job_id}")
        
        return {"job": {"id": job_id, "status": "CANCELLED"}}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel job error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel job")
```

### 6.2 Worker Cancellation Checks

Workers periodically check for cancellation flag at each processing stage (as shown in the task implementation above).

---

## 7. File Storage Abstraction

**File**: `backend/app/services/storage_service.py`

```python
from abc import ABC, abstractmethod
from fastapi import UploadFile
import os
import shutil
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class StorageBackend(ABC):
    """Abstract storage backend"""
    
    @abstractmethod
    async def save_file(self, file: UploadFile, filename: str, folder: str = "") -> str:
        """Save file and return path"""
        pass
    
    @abstractmethod
    async def get_file(self, file_path: str) -> bytes:
        """Retrieve file content"""
        pass
    
    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Delete file"""
        pass
    
    @abstractmethod
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        pass

class LocalStorageBackend(StorageBackend):
    """Local filesystem storage"""
    
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    async def save_file(self, file: UploadFile, filename: str, folder: str = "") -> str:
        """Save file to local filesystem"""
        folder_path = os.path.join(self.base_path, folder)
        os.makedirs(folder_path, exist_ok=True)
        
        file_path = os.path.join(folder_path, filename)
        
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        
        logger.info(f"Saved file to {file_path}")
        return file_path
    
    async def get_file(self, file_path: str) -> bytes:
        """Read file from local filesystem"""
        with open(file_path, 'rb') as f:
            return f.read()
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from local filesystem"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        return os.path.exists(file_path)

class S3StorageBackend(StorageBackend):
    """AWS S3 storage"""
    
    def __init__(self, bucket_name: str, aws_access_key: str, aws_secret_key: str, region: str):
        import boto3
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region
        )
    
    async def save_file(self, file: UploadFile, filename: str, folder: str = "") -> str:
        """Upload file to S3"""
        s3_key = f"{folder}/{filename}" if folder else filename
        
        self.s3_client.upload_fileobj(file.file, self.bucket_name, s3_key)
        
        logger.info(f"Uploaded file to S3: {s3_key}")
        return s3_key
    
    async def get_file(self, file_path: str) -> bytes:
        """Download file from S3"""
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
        return response['Body'].read()
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            logger.info(f"Deleted file from S3: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting S3 file: {e}")
            return False
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except:
            return False

class StorageService:
    """Storage service with backend abstraction"""
    
    def __init__(self):
        if settings.STORAGE_TYPE == "s3":
            self.backend = S3StorageBackend(
                bucket_name=settings.AWS_S3_BUCKET,
                aws_access_key=settings.AWS_ACCESS_KEY_ID,
                aws_secret_key=settings.AWS_SECRET_ACCESS_KEY,
                region=settings.AWS_REGION
            )
        else:
            self.backend = LocalStorageBackend(settings.LOCAL_STORAGE_PATH)
    
    async def save_file(self, file: UploadFile, filename: str, folder: str = "") -> str:
        return await self.backend.save_file(file, filename, folder)
    
    async def get_file(self, file_path: str) -> bytes:
        return await self.backend.get_file(file_path)
    
    async def delete_file(self, file_path: str) -> bool:
        return await self.backend.delete_file(file_path)
    
    async def file_exists(self, file_path: str) -> bool:
        return await self.backend.file_exists(file_path)
```

---

## Summary

This Low-Level Design provides:

✅ **Detailed Component Implementation**: Complete code structure for frontend and backend  
✅ **Authentication Integration**: Clerk auth with JWT validation  
✅ **WebSocket Communication**: Real-time progress updates with fallback  
✅ **Celery Task Processing**: Multi-stage document processing with progress tracking  
✅ **File Storage Abstraction**: Swappable local/S3 storage backends  
✅ **Idempotency**: Safe retry mechanisms for task execution  
✅ **Cancellation Support**: User-initiated job cancellation  
✅ **Testing Framework**: Unit test structure and examples  
✅ **Docker Deployment**: Complete Docker Compose setup  
✅ **Error Handling**: Comprehensive error handling and logging  

The implementation is production-ready and follows best practices for async workflow systems.
