# High-Level Design (HLD)
## Async Document Processing Workflow System

---

## 1. System Overview

### 1.1 Purpose
Build a production-grade full-stack application that enables users to upload documents, process them asynchronously in the background, track progress in real-time, review/edit extracted data, and export finalized results.

### 1.2 Key Objectives
- **Asynchronous Processing**: Decouple document processing from HTTP request/response cycle
- **Real-time Progress**: Live tracking of background jobs via WebSocket
- **Scalability**: Horizontal scaling of worker nodes
- **Reliability**: Idempotent operations, retry mechanisms, and cancellation support
- **User Experience**: Intuitive UI with live feedback and editing capabilities

---

## 2. Architecture Overview

### 2.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  React Frontend (TypeScript)                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Upload UI  │  │  Dashboard   │  │ Detail/Edit  │                  │
│  │              │  │  (List/Filter│  │   Review     │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│         │                  │                  │                          │
│         └──────────────────┼──────────────────┘                          │
│                            │                                             │
│                   ┌────────▼────────┐                                    │
│                   │  Clerk Auth     │                                    │
│                   │  (JWT tokens)   │                                    │
│                   └────────┬────────┘                                    │
│                            │                                             │
│                   ┌────────▼────────┐                                    │
│                   │  WebSocket      │                                    │
│                   │  Connection     │                                    │
│                   └────────┬────────┘                                    │
└────────────────────────────┼────────────────────────────────────────────┘
                             │
                             │ HTTPS / WSS
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                        APPLICATION LAYER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  FastAPI Backend                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  REST API    │  │  WebSocket   │  │ File Upload  │                  │
│  │  Endpoints   │  │  Manager     │  │  Handler     │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                  │                          │
│         └──────────────────┼──────────────────┘                          │
│                            │                                             │
│                   ┌────────▼────────┐                                    │
│                   │ Service Layer   │                                    │
│                   │ (Business Logic)│                                    │
│                   └────────┬────────┘                                    │
│                            │                                             │
│         ┌──────────────────┼──────────────────┐                          │
│         │                  │                  │                          │
│  ┌──────▼───────┐  ┌──────▼──────┐  ┌───────▼──────┐                   │
│  │   Prisma     │  │   Celery    │  │    Redis     │                   │
│  │   Client     │  │   Client    │  │   Client     │                   │
│  └──────┬───────┘  └──────┬──────┘  └───────┬──────┘                   │
└─────────┼──────────────────┼──────────────────┼──────────────────────────┘
          │                  │                  │
          │                  │                  │
┌─────────▼────────┐ ┌───────▼────────┐ ┌──────▼───────┐
│                  │ │                 │ │              │
│  PostgreSQL      │ │  Celery Worker  │ │    Redis     │
│  (Neon DB)       │ │     Pool        │ │   (Broker)   │
│                  │ │                 │ │              │
│  - Documents     │ │  ┌───────────┐  │ │  - Task Queue│
│  - Jobs          │ │  │  Worker 1 │  │ │  - Pub/Sub   │
│  - Users         │ │  │  Worker 2 │  │ │  - Progress  │
│  - Progress      │ │  │  Worker N │  │ │  - Cache     │
│                  │ │  └───────────┘  │ │              │
└──────────────────┘ └─────────┬───────┘ └──────────────┘
                               │
                               │
                    ┌──────────▼──────────┐
                    │  File Storage       │
                    │  (Local/S3 Abstract)│
                    │  - Uploads/         │
                    │  - Processed/       │
                    └─────────────────────┘
```

### 2.2 Component Interaction Flow

#### Document Upload Flow
1. User uploads document(s) via React UI
2. Frontend sends multipart form data to FastAPI `/api/documents/upload`
3. FastAPI validates file, stores in file storage, creates DB record
4. FastAPI dispatches Celery task and returns job ID
5. Frontend opens WebSocket connection to track progress
6. Celery worker picks up task and starts processing
7. Worker publishes progress events to Redis Pub/Sub
8. FastAPI WebSocket manager consumes events and broadcasts to connected clients
9. Frontend receives real-time updates and updates UI
10. On completion, user can review/edit/export results

---

## 3. Technology Stack

### 3.1 Frontend
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | React 18+ with TypeScript | UI component library |
| **Build Tool** | Vite | Fast development and optimized builds |
| **State Management** | TanStack Query (React Query) | Server state management, caching |
| **WebSocket** | native WebSocket API | Real-time progress updates |
| **HTTP Client** | Axios | REST API communication |
| **Authentication** | Clerk React SDK | User authentication and session management |
| **UI Components** | shadcn/ui + Tailwind CSS | Pre-built accessible components |
| **Form Handling** | React Hook Form + Zod | Type-safe form validation |
| **Routing** | React Router v6 | Client-side routing |
| **File Upload** | react-dropzone | Drag-and-drop file upload |
| **Data Display** | TanStack Table | Advanced table with sorting/filtering |

### 3.2 Backend
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | FastAPI 0.104+ | High-performance async web framework |
| **Language** | Python 3.11+ | Backend language |
| **ORM** | Prisma (via Prisma Client Python) | Type-safe database access |
| **Database** | PostgreSQL (Neon DB) | Primary data store |
| **Task Queue** | Celery 5.3+ | Distributed task queue |
| **Message Broker** | Redis 7+ | Celery broker and Pub/Sub |
| **WebSocket** | FastAPI WebSocket + python-socketio | Real-time bidirectional communication |
| **Authentication** | Clerk Python SDK | JWT validation and user management |
| **File Processing** | PyPDF2, python-docx, Pillow, pytesseract | Document parsing |
| **Validation** | Pydantic v2 | Request/response validation |
| **Testing** | pytest + pytest-asyncio | Unit testing |

### 3.3 Infrastructure
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Containerization** | Docker + Docker Compose | Local development and deployment |
| **File Storage** | Local filesystem (abstracted for S3) | Document storage |
| **Monitoring** | Flower (Celery) | Worker monitoring dashboard |
| **CORS** | FastAPI CORS middleware | Cross-origin resource sharing |

---

## 4. Core System Components

### 4.1 Frontend Architecture

```
src/
├── components/
│   ├── ui/                 # shadcn/ui components
│   ├── upload/
│   │   ├── FileUploader.tsx
│   │   └── UploadProgress.tsx
│   ├── dashboard/
│   │   ├── DocumentList.tsx
│   │   ├── StatusFilter.tsx
│   │   └── SearchBar.tsx
│   ├── detail/
│   │   ├── DocumentDetail.tsx
│   │   ├── EditForm.tsx
│   │   └── ProgressTracker.tsx
│   └── layout/
│       ├── Header.tsx
│       └── Sidebar.tsx
├── hooks/
│   ├── useWebSocket.ts     # WebSocket connection management
│   ├── useDocuments.ts     # Document CRUD operations
│   └── useAuth.ts          # Clerk auth wrapper
├── services/
│   ├── api.ts              # Axios instance + interceptors
│   ├── websocket.ts        # WebSocket service
│   └── documentService.ts  # Document API calls
├── types/
│   └── document.ts         # TypeScript interfaces
├── utils/
│   └── formatters.ts
└── pages/
    ├── UploadPage.tsx
    ├── DashboardPage.tsx
    └── DocumentDetailPage.tsx
```

### 4.2 Backend Architecture

```
backend/
├── app/
│   ├── main.py             # FastAPI app initialization
│   ├── config.py           # Configuration management
│   ├── dependencies.py     # Dependency injection
│   │
│   ├── api/
│   │   ├── v1/
│   │   │   ├── documents.py    # Document endpoints
│   │   │   ├── jobs.py         # Job management
│   │   │   ├── export.py       # Export endpoints
│   │   │   └── websocket.py    # WebSocket endpoint
│   │   └── deps.py             # API dependencies
│   │
│   ├── core/
│   │   ├── auth.py             # Clerk integration
│   │   ├── security.py         # Security utilities
│   │   └── websocket_manager.py # WebSocket connection pool
│   │
│   ├── services/
│   │   ├── document_service.py # Document business logic
│   │   ├── job_service.py      # Job management
│   │   ├── export_service.py   # Export logic
│   │   └── storage_service.py  # File storage abstraction
│   │
│   ├── workers/
│   │   ├── celery_app.py       # Celery configuration
│   │   ├── tasks.py            # Celery task definitions
│   │   └── processors/
│   │       ├── pdf_processor.py
│   │       ├── docx_processor.py
│   │       ├── image_processor.py
│   │       └── base_processor.py
│   │
│   ├── models/              # Prisma-generated models
│   │   └── (generated by Prisma)
│   │
│   ├── schemas/
│   │   ├── document.py         # Pydantic schemas
│   │   ├── job.py
│   │   └── progress.py
│   │
│   └── utils/
│       ├── file_utils.py
│       ├── redis_client.py     # Redis utility
│       └── exceptions.py
│
├── prisma/
│   └── schema.prisma           # Database schema
│
├── tests/
│   ├── unit/
│   │   ├── test_services/
│   │   ├── test_processors/
│   │   └── test_utils/
│   └── conftest.py
│
└── alembic/                    # Database migrations (if needed)
```

---

## 5. Data Architecture

### 5.1 Database Schema (Prisma)

```prisma
// User information synced from Clerk
model User {
  id        String   @id @default(uuid())
  clerkId   String   @unique
  email     String   @unique
  firstName String?
  lastName  String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  documents Document[]

  @@index([clerkId])
  @@index([email])
}

// Document metadata
model Document {
  id           String   @id @default(uuid())
  userId       String
  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  
  filename     String
  originalName String
  fileType     String
  fileSize     Int
  filePath     String
  
  status       DocumentStatus @default(PENDING)
  
  uploadedAt   DateTime @default(now())
  updatedAt    DateTime @updatedAt
  
  job          Job?
  processedData ProcessedData?

  @@index([userId])
  @@index([status])
  @@index([uploadedAt])
}

enum DocumentStatus {
  PENDING
  QUEUED
  PROCESSING
  COMPLETED
  FAILED
  CANCELLED
}

// Processing job
model Job {
  id           String   @id @default(uuid())
  documentId   String   @unique
  document     Document @relation(fields: [documentId], references: [id], onDelete: Cascade)
  
  celeryTaskId String   @unique
  status       JobStatus @default(PENDING)
  
  retryCount   Int      @default(0)
  maxRetries   Int      @default(3)
  
  startedAt    DateTime?
  completedAt  DateTime?
  failedAt     DateTime?
  
  errorMessage String?
  
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
  
  progressEvents ProgressEvent[]

  @@index([celeryTaskId])
  @@index([status])
  @@index([createdAt])
}

enum JobStatus {
  PENDING
  QUEUED
  PROCESSING
  COMPLETED
  FAILED
  CANCELLED
  RETRYING
}

// Progress tracking
model ProgressEvent {
  id        String   @id @default(uuid())
  jobId     String
  job       Job      @relation(fields: [jobId], references: [id], onDelete: Cascade)
  
  eventType String
  message   String
  progress  Int      @default(0) // 0-100
  metadata  Json?
  
  timestamp DateTime @default(now())

  @@index([jobId])
  @@index([timestamp])
}

// Extracted and processed data
model ProcessedData {
  id           String   @id @default(uuid())
  documentId   String   @unique
  document     Document @relation(fields: [documentId], references: [id], onDelete: Cascade)
  
  extractedText String?
  
  // Structured fields
  title        String?
  category     String?
  summary      String?
  keywords     String[] // Array of strings
  
  metadata     Json?    // Additional metadata
  
  isReviewed   Boolean  @default(false)
  isFinalized  Boolean  @default(false)
  
  reviewedAt   DateTime?
  finalizedAt  DateTime?
  
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt

  @@index([documentId])
  @@index([isFinalized])
}
```

### 5.2 Redis Data Structures

```
# Task Queue (managed by Celery)
celery:task:{task_id} -> Task metadata

# Job Progress (Pub/Sub)
progress:{job_id} -> Channel for progress events

# Progress State (for polling fallback)
job:progress:{job_id} -> Hash with current state
  - status: "processing"
  - progress: 45
  - current_step: "extraction_started"
  - message: "Extracting text from document"
  - updated_at: timestamp

# Active WebSocket Connections
ws:connections:{user_id} -> Set of connection IDs

# Job Cancellation Flags
job:cancel:{job_id} -> "1" (exists = cancelled)

# Rate Limiting (optional)
ratelimit:upload:{user_id} -> Counter with TTL
```

---

## 6. API Design

### 6.1 REST API Endpoints

#### Authentication
All endpoints require `Authorization: Bearer <Clerk JWT>` header

#### Document Management

**POST /api/v1/documents/upload**
```json
Request: multipart/form-data
{
  "files": [File, File, ...],
  "metadata": {
    "category": "invoice"  // optional
  }
}

Response: 201 Created
{
  "documents": [
    {
      "id": "doc-uuid",
      "filename": "document.pdf",
      "status": "queued",
      "job": {
        "id": "job-uuid",
        "status": "queued"
      }
    }
  ]
}
```

**GET /api/v1/documents**
```json
Query Parameters:
  - status: "completed" | "processing" | "failed"
  - search: "keyword"
  - sort: "uploadedAt" | "filename"
  - order: "asc" | "desc"
  - page: 1
  - limit: 20

Response: 200 OK
{
  "documents": [
    {
      "id": "doc-uuid",
      "filename": "document.pdf",
      "fileType": "application/pdf",
      "fileSize": 1024000,
      "status": "completed",
      "uploadedAt": "2024-01-01T00:00:00Z",
      "job": {
        "id": "job-uuid",
        "status": "completed",
        "completedAt": "2024-01-01T00:05:00Z"
      }
    }
  ],
  "pagination": {
    "total": 100,
    "page": 1,
    "limit": 20,
    "pages": 5
  }
}
```

**GET /api/v1/documents/{document_id}**
```json
Response: 200 OK
{
  "id": "doc-uuid",
  "filename": "document.pdf",
  "fileType": "application/pdf",
  "fileSize": 1024000,
  "status": "completed",
  "uploadedAt": "2024-01-01T00:00:00Z",
  "job": {
    "id": "job-uuid",
    "status": "completed",
    "progress": 100,
    "startedAt": "2024-01-01T00:00:00Z",
    "completedAt": "2024-01-01T00:05:00Z"
  },
  "processedData": {
    "title": "Invoice #12345",
    "category": "invoice",
    "summary": "Invoice for services rendered...",
    "keywords": ["invoice", "payment", "services"],
    "extractedText": "Full text...",
    "isReviewed": false,
    "isFinalized": false
  }
}
```

**DELETE /api/v1/documents/{document_id}**
```json
Response: 204 No Content
```

#### Job Management

**POST /api/v1/jobs/{job_id}/retry**
```json
Response: 200 OK
{
  "job": {
    "id": "job-uuid",
    "status": "queued",
    "retryCount": 1
  }
}
```

**POST /api/v1/jobs/{job_id}/cancel**
```json
Response: 200 OK
{
  "job": {
    "id": "job-uuid",
    "status": "cancelled"
  }
}
```

**GET /api/v1/jobs/{job_id}/progress**
```json
Response: 200 OK
{
  "jobId": "job-uuid",
  "status": "processing",
  "progress": 60,
  "currentStep": "extraction_started",
  "message": "Extracting structured fields",
  "events": [
    {
      "eventType": "job_started",
      "message": "Job started",
      "progress": 0,
      "timestamp": "2024-01-01T00:00:00Z"
    },
    {
      "eventType": "parsing_completed",
      "message": "Document parsed successfully",
      "progress": 40,
      "timestamp": "2024-01-01T00:02:00Z"
    }
  ]
}
```

#### Review & Finalize

**PUT /api/v1/documents/{document_id}/processed-data**
```json
Request:
{
  "title": "Updated Title",
  "category": "invoice",
  "summary": "Updated summary",
  "keywords": ["new", "keywords"]
}

Response: 200 OK
{
  "processedData": {
    "id": "data-uuid",
    "title": "Updated Title",
    "category": "invoice",
    "summary": "Updated summary",
    "keywords": ["new", "keywords"],
    "isReviewed": true
  }
}
```

**POST /api/v1/documents/{document_id}/finalize**
```json
Response: 200 OK
{
  "processedData": {
    "id": "data-uuid",
    "isFinalized": true,
    "finalizedAt": "2024-01-01T00:10:00Z"
  }
}
```

#### Export

**GET /api/v1/export/json**
```json
Query Parameters:
  - documentIds: ["uuid1", "uuid2"]  // optional, all finalized if not provided

Response: 200 OK (application/json)
[
  {
    "documentId": "doc-uuid",
    "filename": "document.pdf",
    "processedData": {
      "title": "Invoice #12345",
      "category": "invoice",
      "summary": "...",
      "keywords": ["..."]
    },
    "exportedAt": "2024-01-01T00:15:00Z"
  }
]
```

**GET /api/v1/export/csv**
```json
Query Parameters:
  - documentIds: ["uuid1", "uuid2"]

Response: 200 OK (text/csv)
documentId,filename,title,category,summary,keywords,exportedAt
doc-uuid,document.pdf,"Invoice #12345",invoice,"...",invoice;payment,2024-01-01T00:15:00Z
```

### 6.2 WebSocket Protocol

**Connection Endpoint**: `ws://localhost:8000/api/v1/ws?token={clerk_jwt}`

**Client → Server Messages**
```json
// Subscribe to job updates
{
  "type": "subscribe",
  "jobId": "job-uuid"
}

// Unsubscribe
{
  "type": "unsubscribe",
  "jobId": "job-uuid"
}

// Ping (keepalive)
{
  "type": "ping"
}
```

**Server → Client Messages**
```json
// Progress update
{
  "type": "progress",
  "jobId": "job-uuid",
  "data": {
    "status": "processing",
    "progress": 60,
    "eventType": "extraction_started",
    "message": "Extracting structured fields",
    "timestamp": "2024-01-01T00:03:00Z"
  }
}

// Job completed
{
  "type": "job_completed",
  "jobId": "job-uuid",
  "data": {
    "status": "completed",
    "completedAt": "2024-01-01T00:05:00Z"
  }
}

// Job failed
{
  "type": "job_failed",
  "jobId": "job-uuid",
  "data": {
    "status": "failed",
    "error": "Error message",
    "failedAt": "2024-01-01T00:05:00Z"
  }
}

// Pong
{
  "type": "pong"
}
```

---

## 7. Processing Pipeline

### 7.1 Document Processing Stages

```
Stage 1: Document Received (0%)
├─ Validate file type and size
├─ Store in file storage
└─ Create database records

Stage 2: Parsing Started (10%)
├─ Load document from storage
├─ Detect document type
└─ Initialize appropriate processor

Stage 3: Parsing Completed (40%)
├─ Extract raw text content
├─ Extract embedded images (if any)
└─ Store parsed content

Stage 4: Extraction Started (50%)
├─ Analyze document structure
├─ Extract metadata (title, dates, etc.)
└─ Identify document category

Stage 5: Extraction Completed (90%)
├─ Generate summary (using simple extraction or AI)
├─ Extract keywords
└─ Create structured output

Stage 6: Final Result Stored (95%)
├─ Save ProcessedData to database
└─ Update document and job status

Stage 7: Job Completed (100%)
├─ Publish completion event
└─ Clean up temporary resources
```

### 7.2 File Type Processing Logic

| File Type | Processing Approach |
|-----------|---------------------|
| **PDF** | PyPDF2 for text extraction, pypdfium2 for image rasterization, pytesseract for OCR on image-based PDFs |
| **DOCX** | python-docx for text/tables/images extraction |
| **TXT** | Direct text read with encoding detection |
| **Images (JPG, PNG)** | pytesseract for OCR, Pillow for image processing |
| **CSV/Excel** | pandas for structured data extraction |
| **HTML** | BeautifulSoup4 for content extraction |

### 7.3 Idempotency Strategy

Each task execution checks:
1. **Job Status Check**: Before starting, verify job is not already processing/completed
2. **Task ID Tracking**: Store Celery task ID in database
3. **Duplicate Detection**: If task with same document ID exists, skip or join existing task
4. **Retry Safety**: On retry, clean up partial results before reprocessing
5. **State Reconciliation**: On worker restart, check for orphaned processing jobs

---

## 8. Real-time Progress Tracking

### 8.1 Progress Event Flow

```
[Celery Worker]
      │
      │ 1. Worker publishes progress event
      ▼
[Redis Pub/Sub Channel: progress:{job_id}]
      │
      │ 2. FastAPI listener subscribed to channel
      ▼
[WebSocket Manager]
      │
      │ 3. Manager identifies connected clients for this job
      ▼
[WebSocket Connections]
      │
      │ 4. Broadcast to all subscribed clients
      ▼
[React Frontend]
      │
      │ 5. Update UI with progress
      ▼
[Progress Bar / Status Display]
```

### 8.2 Fallback Mechanism

If WebSocket connection fails:
1. Frontend falls back to polling `/api/v1/jobs/{job_id}/progress` every 2 seconds
2. Progress events are stored in Redis with TTL (60 minutes)
3. Polling endpoint reads from Redis cache or database

---

## 9. Error Handling & Resilience

### 9.1 Retry Strategy

| Error Type | Retry Strategy | Max Retries |
|------------|----------------|-------------|
| **Network Error** | Exponential backoff (2s, 4s, 8s) | 3 |
| **File Read Error** | Immediate retry once | 1 |
| **Parsing Error** | No retry (mark as failed) | 0 |
| **Database Error** | Exponential backoff | 3 |
| **Resource Exhaustion** | Delay 30s, then retry | 2 |

### 9.2 Failure Scenarios

1. **Worker Crash**: Celery task timeout (30 minutes), mark job as failed
2. **Database Unavailable**: Queue tasks, retry with exponential backoff
3. **Redis Down**: Tasks still queued, progress tracking degraded
4. **File Storage Unavailable**: Fail fast, allow manual retry
5. **Large File Timeout**: Stream processing with checkpoints

### 9.3 Cancellation Support

1. User clicks "Cancel" button
2. Frontend sends `POST /api/v1/jobs/{job_id}/cancel`
3. Backend sets `job:cancel:{job_id}` flag in Redis
4. Worker checks flag at each processing stage
5. If flag set, worker terminates gracefully and updates job status

---

## 10. Security Considerations

### 10.1 Authentication & Authorization
- **Clerk JWT Validation**: All API endpoints validate Clerk JWT tokens
- **User Isolation**: Users can only access their own documents
- **Row-Level Security**: Database queries filtered by user ID

### 10.2 File Upload Security
- **File Type Validation**: Whitelist of allowed MIME types
- **File Size Limits**: 50MB per file, 200MB per upload batch
- **Virus Scanning**: Optional integration with ClamAV
- **Path Traversal Prevention**: Sanitize filenames

### 10.3 Rate Limiting
- **Upload Rate**: 10 files per minute per user
- **API Rate**: 100 requests per minute per user
- **WebSocket Connections**: Max 5 concurrent connections per user

---

## 11. Scalability & Performance

### 11.1 Horizontal Scaling

**Frontend**: Stateless, can scale horizontally behind load balancer

**Backend**: 
- Stateless API servers (except WebSocket connections)
- Use Redis for session sharing
- Sticky sessions for WebSocket connections

**Workers**:
- Scale workers based on queue length
- Auto-scaling with Kubernetes HPA or Docker Swarm
- Dedicated worker pools for different document types

**Database**:
- Neon DB serverless auto-scaling
- Read replicas for analytics queries
- Connection pooling (PgBouncer)

### 11.2 Performance Optimizations

- **File Upload**: Chunked upload for large files
- **Caching**: Redis cache for frequently accessed documents
- **Database Indexing**: Indexes on user_id, status, created_at
- **Lazy Loading**: Paginated results with cursor-based pagination
- **CDN**: Serve static assets from CDN
- **Compression**: Gzip/Brotli compression for API responses

---

## 12. Monitoring & Observability

### 12.1 Metrics to Track
- Upload success/failure rate
- Average processing time per document type
- Worker queue length and processing rate
- API response times (p50, p95, p99)
- WebSocket connection count
- Error rates by endpoint
- Database query performance

### 12.2 Logging Strategy
- **Structured Logging**: JSON format with correlation IDs
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Context**: Include user_id, document_id, job_id in all logs
- **Retention**: 30 days for application logs, 90 days for audit logs

### 12.3 Health Checks
- `/health` endpoint for basic health check
- `/health/deep` for database, Redis, and worker connectivity
- Flower dashboard for Celery worker monitoring

---

## 13. Deployment Architecture

### 13.1 Docker Compose Services

```yaml
services:
  - frontend:      React app (Nginx)
  - backend:       FastAPI application
  - worker:        Celery worker (scalable)
  - redis:         Redis server
  - postgres:      PostgreSQL (or external Neon DB)
  - flower:        Celery monitoring UI
```

### 13.2 Environment Configuration

```
Development:
  - Local Docker Compose
  - Hot reload enabled
  - Debug mode on

Staging:
  - Docker Compose on cloud VM
  - Reduced resource limits
  - Clerk test environment

Production:
  - Kubernetes cluster or cloud container service
  - Auto-scaling enabled
  - Clerk production environment
  - External managed PostgreSQL (Neon DB)
  - External Redis (Redis Cloud or AWS ElastiCache)
```

---

## 14. Trade-offs & Design Decisions

### 14.1 Prisma vs SQLAlchemy
**Choice**: Prisma
- **Pros**: Type-safe, auto-generated client, migration management
- **Cons**: Less Python-native than SQLAlchemy, smaller community
- **Rationale**: Type safety and modern DX outweigh ecosystem size

### 14.2 WebSocket vs SSE vs Polling
**Choice**: WebSocket with polling fallback
- **Pros**: True bidirectional communication, lowest latency
- **Cons**: More complex to implement and scale
- **Rationale**: Best user experience for real-time updates

### 14.3 Local Storage vs S3
**Choice**: Abstraction layer supporting both
- **Pros**: Flexibility for different deployment scenarios
- **Cons**: Additional abstraction complexity
- **Rationale**: Easy local development, production-ready for cloud

### 14.4 Monolithic vs Microservices
**Choice**: Monolithic with clear service boundaries
- **Pros**: Simpler deployment, easier development for small team
- **Cons**: Harder to scale individual components
- **Rationale**: Premature optimization avoided, can split later

---

## 15. Future Enhancements

1. **AI-Powered Processing**: Integrate LLMs for better summarization and classification
2. **Batch Operations**: Bulk upload, retry, export
3. **Collaboration**: Share documents between users
4. **Version History**: Track changes to processed data
5. **Custom Workflows**: User-defined processing pipelines
6. **Advanced Search**: Full-text search with Elasticsearch
7. **Webhook Notifications**: Notify external systems on completion
8. **Multi-tenancy**: Organization-level isolation
9. **Audit Logs**: Comprehensive activity tracking
10. **Custom Exports**: User-defined export templates

---

## Summary

This HLD provides a comprehensive blueprint for building a production-grade async document processing system. The architecture prioritizes:

✅ **Reliability**: Retry mechanisms, idempotency, error handling  
✅ **Scalability**: Horizontal scaling of all components  
✅ **User Experience**: Real-time updates, intuitive UI  
✅ **Security**: Authentication, authorization, input validation  
✅ **Maintainability**: Clean architecture, separation of concerns  
✅ **Observability**: Logging, monitoring, health checks  

The system is designed to handle thousands of concurrent document processing jobs while providing a seamless user experience with live progress tracking and comprehensive document management capabilities.
