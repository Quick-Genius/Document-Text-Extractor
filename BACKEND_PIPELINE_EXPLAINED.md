# Complete Backend Pipeline Explanation

## Architecture Overview

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐      ┌──────────────┐
│   Frontend  │─────▶│  FastAPI     │─────▶│   Celery    │─────▶│  AI/Gemini   │
│   (React)   │      │   Server     │      │   Worker    │      │  Processing  │
└─────────────┘      └──────────────┘      └─────────────┘      └──────────────┘
                            │                      │                      │
                            ▼                      ▼                      ▼
                     ┌──────────────┐      ┌─────────────┐      ┌──────────────┐
                     │   Neon DB    │      │    Redis    │      │   S3/Local   │
                     │  (Postgres)  │      │   (Queue)   │      │   Storage    │
                     └──────────────┘      └─────────────┘      └──────────────┘
```

## Tech Stack

- **Web Framework**: FastAPI (Python async)
- **Database**: Neon PostgreSQL (serverless)
- **ORM**: Prisma (Python client)
- **Task Queue**: Celery + Redis
- **Storage**: AWS S3 or Local filesystem
- **Auth**: Clerk (JWT tokens)
- **AI**: Google Gemini 1.5
- **WebSocket**: FastAPI WebSocket + Redis Pub/Sub

---

## 1. Document Upload Flow

### Step 1: User Uploads Document(s)

**Endpoint**: `POST /api/v1/documents/upload`

```python
# File: backend/app/api/v1/documents.py

@router.post("/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id)
):
```

**What Happens**:
1. Frontend sends files via multipart/form-data
2. FastAPI receives files + auth token
3. Validates:
   - Max 10 files per upload
   - Max 50MB per file
   - Allowed file types (PDF, DOCX, images, text, CSV, HTML)

### Step 2: Authentication

```python
# File: backend/app/core/auth.py

async def get_current_user_id(authorization: str = Header(None)):
    # Extracts Bearer token
    # Validates with Clerk (or returns "dev-user-id" in dev mode)
    # Returns user_id
```

**Auth Flow**:
- Production: Validates JWT with Clerk API
- Development: Returns mock user ID for testing

### Step 3: Document Service Processing

```python
# File: backend/app/services/document_service.py

async def create_documents_from_upload(
    user_id: str,
    files: List[UploadFile],
    category: Optional[str] = None
):
```

**What Happens**:

#### A. User Lookup/Creation
```python
user = await db.user.find_unique(where={"clerkId": user_id})
if not user:
    user = await db.user.create(...)
```

#### B. Rate Limiting (Batch Uploads Only)
```python
if len(files) >= 2:
    pending_count = await db.document.count(
        where={"status": {"in": ["PENDING", "PROCESSING"]}}
    )
    if pending_count >= MAX_QUEUE_DEPTH:
        raise ValidationError("System overloaded")
```

**Purpose**: Prevent system overload from too many concurrent uploads

#### C. File Storage
```python
# File: backend/app/services/storage_service.py

file_path = await self.storage.save_file(
    file=file,
    filename=stored_filename,
    folder="uploads"
)
```

**Storage Options**:
- **S3**: Uploads to AWS S3 bucket (production)
- **Local**: Saves to `backend/storage/uploads/` (development)

#### D. Database Transaction (Batch Uploads)

For 2+ files, uses PostgreSQL transaction:

```python
async with db.tx(timeout=timedelta(seconds=30)) as transaction:
    for file in files:
        # Create document record
        document = await transaction.document.create(...)
        
        # Create job record
        job = await transaction.job.create(...)
        
        # Store for later task enqueuing
        created_docs.append({...})
```

**Why Transaction?**
- Ensures all documents are created atomically
- If one fails, all rollback
- Prevents partial batch uploads

#### E. Celery Task Enqueuing

After transaction commits:

```python
for doc_info in created_docs:
    task_result = process_document_task.delay(
        document_id=doc_info["document_id"],
        file_path=doc_info["file_path"]
    )
    
    # Update job with actual Celery task ID
    await db.job.update(
        where={"id": doc_info["job_id"]},
        data={"celeryTaskId": task_result.id}
    )
```

**Task Queue**:
- Tasks sent to Redis queue
- Celery worker picks them up
- Up to 4 tasks process concurrently

---

## 2. Celery Worker Processing

### Worker Configuration

```python
# File: backend/app/workers/celery_app.py

celery_app.conf.update(
    worker_concurrency=4,           # 4 tasks at once
    worker_prefetch_multiplier=1,   # Fair distribution
    task_acks_late=True,            # Reliability
    task_time_limit=3600,           # 1 hour timeout
)
```

### Task Execution

```python
# File: backend/app/workers/tasks.py

@celery_app.task(bind=True, name="app.workers.tasks.process_document_task")
def process_document_task(self, document_id: str, file_path: str):
    # Runs in separate worker process
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        process_document_async(self, document_id, file_path)
    )
    return result
```

### Processing Pipeline

#### Stage 1: Database Connection
```python
db = get_prisma_with_pool()
await connect_prisma_with_timeout(db, timeout=PRISMA_POOL_TIMEOUT)
```

**Connection Pooling**:
- Reuses database connections
- Prevents connection exhaustion
- Timeout protection (10 seconds)

#### Stage 2: Distributed Locking
```python
lock_name = f"document:processing:lock"
lock = await redis_client.acquire_lock(
    lock_name, 
    timeout=TASK_TOTAL_TIMEOUT
)
```

**Purpose**:
- Limits concurrent task execution
- Prevents resource exhaustion
- Coordinates across multiple workers

#### Stage 3: Status Update
```python
await db.document.update(
    where={"id": document_id},
    data={"status": "PROCESSING"}
)

await db.job.update(
    where={"id": job.id},
    data={"status": "PROCESSING"}
)
```

#### Stage 4: File Download (if S3)
```python
if file_path.startswith("http"):
    local_file_path = download_remote_file(file_path)
    temp_file_created = True
```

**S3 Download**:
- Downloads file from S3 to temp location
- Uses boto3 client
- Cleans up after processing

#### Stage 5: Document Parsing

```python
# Determine processor based on file type
if file_type == "application/pdf":
    processor = PDFProcessor()
elif file_type == "application/vnd.openxmlformats...":
    processor = DOCXProcessor()
elif file_type.startswith("image/"):
    processor = ImageProcessor()
else:
    processor = TextProcessor()

# Extract text
extracted_text = await processor.extract_text(local_file_path)
```

**Processors**:
- **PDFProcessor**: Uses PyPDF2 + pdf2image + pytesseract (OCR)
- **DOCXProcessor**: Uses python-docx
- **ImageProcessor**: Uses Pillow + pytesseract (OCR)
- **TextProcessor**: Direct file read

#### Stage 6: AI Processing (Gemini)

```python
# File: backend/app/workers/processors/base_processor.py

async def process_with_gemini(self, text: str):
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    Analyze this document and extract:
    - Title
    - Category
    - Summary
    - Keywords
    - Metadata
    
    Document text:
    {text}
    """
    
    response = await model.generate_content_async(prompt)
    return self._parse_gemini_response(response.text)
```

**AI Extraction**:
- Sends extracted text to Gemini
- Gets structured metadata back
- Parses JSON response
- Calculates confidence score

#### Stage 7: Progress Updates (WebSocket)

Throughout processing:

```python
await redis_client.publish(
    f"progress:{job.id}",
    {
        "type": "stage_update",
        "stage": "parsing",
        "progress": 25,
        "message": "Extracting text..."
    }
)
```

**Real-time Updates**:
- Published to Redis channel
- WebSocket manager listens
- Broadcasts to connected frontend clients
- Shows live progress in UI

#### Stage 8: Save Results

```python
processed_data = await db.processeddata.create(
    data={
        "documentId": document_id,
        "extractedText": extracted_text,
        "title": ai_result["title"],
        "category": ai_result["category"],
        "summary": ai_result["summary"],
        "keywords": ai_result["keywords"],
        "metadata": ai_result["metadata"],
        "confidenceScore": confidence_score,
    }
)

await db.document.update(
    where={"id": document_id},
    data={"status": "COMPLETED"}
)

await db.job.update(
    where={"id": job.id},
    data={"status": "COMPLETED"}
)
```

#### Stage 9: Cleanup

```python
# Release distributed lock
if lock:
    await redis_client.release_lock(lock)

# Delete temp file
if temp_file_created:
    os.remove(local_file_path)

# Disconnect database
await db.disconnect()
```

---

## 3. Error Handling

### Task Failure Handler

```python
def on_failure(self, exc, task_id, args, kwargs, einfo):
    # Update job status to FAILED
    # Store error message
    # Increment retry count
    # Publish failure event
```

### Retry Logic

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
```

**Retry Behavior**:
- Max 3 retries per task
- 60 second delay between retries
- Exponential backoff
- Tracks retry count in database

### Cancellation Support

```python
# Check cancellation flag
cancel_flag = await redis_client.get(f"job:cancel:{job.id}")
if cancel_flag:
    raise TaskCancelled("Task was cancelled by user")
```

**Graceful Shutdown**:
- Checks Redis flag periodically
- Allows task to clean up
- Updates status to CANCELLED

---

## 4. WebSocket Real-Time Updates

### Connection Flow

```python
# File: backend/app/api/v1/websocket.py

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    await websocket_manager.connect(websocket, token)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
```

### Message Broadcasting

```python
# File: backend/app/core/websocket_manager.py

class WebSocketManager:
    async def start(self):
        # Subscribe to Redis pub/sub
        self.pubsub = redis_client.subscribe("progress:*")
        
        # Listen for messages
        asyncio.create_task(self._listen_redis())
    
    async def _listen_redis(self):
        async for message in self.pubsub.listen():
            # Broadcast to connected clients
            await self.broadcast(message)
```

**Real-time Flow**:
1. Worker publishes progress to Redis
2. WebSocket manager listens to Redis
3. Manager broadcasts to all connected clients
4. Frontend receives and updates UI

---

## 5. Database Schema

### Core Tables

```prisma
// File: backend/prisma/schema.prisma

model User {
  id        String   @id @default(uuid())
  clerkId   String   @unique
  email     String
  documents Document[]
}

model Document {
  id            String   @id @default(uuid())
  userId        String
  filename      String
  originalName  String
  fileType      String
  fileSize      Int
  filePath      String
  status        String   // PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED
  uploadedAt    DateTime @default(now())
  updatedAt     DateTime @updatedAt
  
  user          User     @relation(fields: [userId], references: [id])
  job           Job?
  processedData ProcessedData?
}

model Job {
  id            String   @id @default(uuid())
  documentId    String   @unique
  celeryTaskId  String
  status        String
  retryCount    Int      @default(0)
  maxRetries    Int      @default(3)
  errorMessage  String?
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
  
  document      Document @relation(fields: [documentId], references: [id])
}

model ProcessedData {
  id              String   @id @default(uuid())
  documentId      String   @unique
  extractedText   String
  title           String?
  category        String?
  summary         String?
  keywords        Json?
  metadata        Json?
  confidenceScore Float?
  isReviewed      Boolean  @default(false)
  isFinalized     Boolean  @default(false)
  
  document        Document @relation(fields: [documentId], references: [id])
}
```

---

## 6. API Endpoints

### Document Management

```
POST   /api/v1/documents/upload          # Upload documents
GET    /api/v1/documents                  # List documents
GET    /api/v1/documents/{id}             # Get document details
DELETE /api/v1/documents/{id}             # Delete document
PUT    /api/v1/documents/{id}/processed-data  # Update extracted data
POST   /api/v1/documents/{id}/finalize    # Lock document from edits
```

### Job Control

```
POST   /api/v1/documents/{id}/cancel      # Cancel processing
POST   /api/v1/documents/{id}/retry       # Retry failed document
GET    /api/v1/jobs/{id}                  # Get job status
```

### Export

```
GET    /api/v1/export/json/{id}           # Export as JSON
GET    /api/v1/export/csv                 # Export multiple as CSV
```

### Admin

```
GET    /api/v1/admin/cleanup-tasks        # Clean stale Celery tasks
GET    /health                            # Health check
```

### WebSocket

```
WS     /api/v1/ws?token={token}           # Real-time updates
```

---

## 7. Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://...
DATABASE_URL_POOLED=postgresql://...-pooler...  # For serverless
DATABASE_URL_DIRECT=postgresql://...            # For long-running

# Redis
REDIS_URL=redis://...
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://...
CELERY_RESULT_BACKEND=redis://...

# Storage
STORAGE_TYPE=s3  # or "local"
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_S3_BUCKET=...

# AI
GEMINI_API_KEY=...

# Auth
CLERK_SECRET_KEY=...

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:5174

# Timeouts
TASK_TIMEOUT=3600
PRISMA_POOL_TIMEOUT=10
BATCH_UPLOAD_MAX_QUEUE_DEPTH=50
```

---

## 8. Performance Optimizations

### Connection Pooling

```python
# File: backend/app/utils/db_pool.py

_prisma_pool = None

def get_prisma_with_pool():
    global _prisma_pool
    if _prisma_pool is None:
        _prisma_pool = Prisma()
    return _prisma_pool
```

**Benefits**:
- Reuses database connections
- Reduces connection overhead
- Prevents connection exhaustion

### Distributed Locking

```python
# Limits concurrent tasks
lock = await redis_client.acquire_lock(
    "document:processing:lock",
    timeout=3600
)
```

**Benefits**:
- Prevents resource exhaustion
- Coordinates across workers
- Ensures system stability

### Transaction Batching

```python
# Batch uploads use single transaction
async with db.tx() as transaction:
    for file in files:
        await transaction.document.create(...)
```

**Benefits**:
- Atomic operations
- Reduced database round-trips
- Better consistency

### Rate Limiting

```python
# Check queue depth before accepting batch
if pending_count >= MAX_QUEUE_DEPTH:
    raise ValidationError("System overloaded")
```

**Benefits**:
- Prevents system overload
- Graceful degradation
- Better user experience

---

## 9. Monitoring & Debugging

### Logging

```python
logger.info(f"Processing document {document_id}")
logger.error(f"Failed to process: {error}", exc_info=True)
```

**Log Levels**:
- INFO: Normal operations
- WARNING: Potential issues
- ERROR: Failures with stack traces

### Celery Inspection

```bash
# Check active tasks
celery -A app.workers.celery_app inspect active

# Check reserved tasks
celery -A app.workers.celery_app inspect reserved

# Check worker stats
celery -A app.workers.celery_app inspect stats
```

### Database Queries

```bash
# Check pending documents
SELECT COUNT(*) FROM "Document" WHERE status IN ('PENDING', 'PROCESSING');

# Check failed jobs
SELECT * FROM "Job" WHERE status = 'FAILED' ORDER BY "updatedAt" DESC;
```

### Redis Monitoring

```bash
# Check queue length
redis-cli LLEN celery

# Check active connections
redis-cli CLIENT LIST
```

---

## 10. Deployment Checklist

### Prerequisites
- [ ] PostgreSQL database (Neon recommended)
- [ ] Redis instance
- [ ] AWS S3 bucket (or local storage)
- [ ] Gemini API key
- [ ] Clerk account (for auth)

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
prisma generate
prisma db push
```

### Start Services
```bash
# Terminal 1: FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Celery worker
celery -A app.workers.celery_app worker --loglevel=info
```

### Verify
```bash
# Health check
curl http://localhost:8000/health

# Upload test
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer test" \
  -F "files=@test.pdf"
```

---

## Summary

The backend pipeline is a sophisticated async document processing system that:

1. **Accepts uploads** via FastAPI REST API
2. **Stores files** in S3 or local storage
3. **Queues tasks** in Redis via Celery
4. **Processes documents** with multiple workers (4 concurrent)
5. **Extracts text** using specialized processors
6. **Analyzes content** with Google Gemini AI
7. **Stores results** in PostgreSQL database
8. **Broadcasts updates** via WebSocket + Redis Pub/Sub
9. **Handles failures** with retry logic and error tracking
10. **Scales horizontally** with multiple workers and connection pooling

The system is designed for reliability, scalability, and real-time user feedback.
