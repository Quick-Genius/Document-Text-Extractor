# DocFlow AI — Intelligent Document Processing Platform

> Transform unstructured documents into structured, queryable data with a production-grade async processing pipeline powered by AI, Celery, RabbitMQ, and real-time WebSocket updates.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Technology Stack](#technology-stack)
4. [System Architecture](#system-architecture)
5. [Detailed System Design](#detailed-system-design)
6. [Application Flow](#application-flow)
7. [Database Design](#database-design)
8. [API Documentation](#api-documentation)
9. [Background Processing](#background-processing)
10. [Infrastructure Architecture](#infrastructure-architecture)
11. [CI/CD Pipeline](#cicd-pipeline)
12. [Local Development Setup](#local-development-setup)
13. [Environment Variables](#environment-variables)
14. [Production Deployment Guide](#production-deployment-guide)
15. [Performance & Scalability](#performance--scalability)
16. [Security Considerations](#security-considerations)
17. [Future Improvements](#future-improvements)
18. [Repository Structure](#repository-structure)

---

## Overview

DocFlow AI is a full-stack, production-grade document intelligence platform that solves a critical enterprise problem: extracting structured, searchable data from raw, unstructured documents at scale.

**The problem it solves:** Organizations receive thousands of PDFs, DOCX files, scanned images, and plain-text documents that contain valuable information locked in an unstructured format. Reading, categorizing, and extracting data from these manually is slow, error-prone, and expensive.

**Who it is for:**

- Engineering teams needing a document ingestion backbone for their product
- Organizations processing invoices, contracts, legal documents, or reports at volume
- Developers building document-aware workflows or AI pipelines
- Startups needing a ready-made, scalable OCR + extraction service

**Core Capabilities:**

- Batch-upload up to 10 documents simultaneously (PDF, DOCX, images, TXT, CSV, HTML)
- Asynchronous processing via a RabbitMQ-backed Celery worker queue
- Multi-stage extraction pipeline: OCR → text parsing → categorization → summarization → keyword extraction
- Groq LLM integration for AI-powered summarization and vision-based OCR fallback
- Real-time progress updates delivered over WebSocket (Redis Pub/Sub backed)
- Automatic stuck-task recovery with a background scheduler
- Dual storage backends: local filesystem for development, AWS S3 for production
- CSV and JSON export of all extracted data
- Clerk-based authentication with per-user document isolation
- Full document lifecycle management: upload → queue → process → review → finalize → export

---

## Features

### Document Processing
- Multi-format ingestion: PDF, DOCX, JPEG, PNG, TXT, CSV, HTML
- PyPDF2 text extraction with automatic OCR fallback via Tesseract for sparse/scanned PDFs
- DOCX paragraph and table extraction via `python-docx`
- Image pre-processing pipeline (greyscale conversion, contrast enhancement, sharpening) before OCR
- Groq LLM Vision fallback (`llama-3.2-11b-vision-preview`) for documents that fail local OCR
- Groq LLM summarization (`llama-3.1-8b-instant`) with a local TF-IDF extractive fallback

### Intelligent Extraction
- Automated title extraction with a multi-signal scoring algorithm (position, capitalisation, length)
- Document category detection across 8 categories: invoice, contract, report, resume, letter, receipt, legal, document
- Extractive or AI-powered summarization (up to 3 sentences)
- TF-IDF keyword extraction with capitalisation bonus for named entities (up to 10 keywords)
- Structured metadata storage: title, category, summary, keywords, confidence score

### Queue Architecture
- RabbitMQ as the Celery message broker with `task_acks_late=True` for at-least-once delivery
- Redis as the Celery result backend and real-time progress store
- Per-worker concurrency of 4 (prefork pool), `prefetch_multiplier=1` for fair task distribution
- `task_reject_on_worker_lost=True` ensures tasks are requeued on worker crash
- Batch upload queue-depth guard (configurable max depth, default 50) with HTTP 429 response

### Real-Time Communication
- WebSocket endpoint backed by Redis Pub/Sub for live progress streaming
- 6-stage progress events: `job_started → parsing_started → parsing_completed → extraction_started → extraction_completed → job_completed`
- Client-side exponential backoff reconnection (up to 5 attempts, capped at 30 s)
- Job subscription model: clients subscribe to specific job IDs

### Reliability & Recovery
- Background `TaskScheduler` runs a recovery sweep every 20 seconds (configurable)
- Detects documents stuck in `PROCESSING`/`QUEUED` state whose Celery task no longer exists
- Self-healing Redis `active_documents` set removes stale or completed entries automatically
- Graceful shutdown: marks all in-flight documents as `FAILED` and purges the Celery queue
- On startup: syncs `active_documents` Redis set from the database

### Document Lifecycle Management
- Cancel a queued or processing document (revokes Celery task with `SIGKILL`)
- Retry failed, cancelled, or completed documents with a new task ID
- Edit extracted data fields before finalizing
- Finalize a document to lock it from further edits
- Permanent or soft delete (clears file path and sets status to `CANCELLED`)
- Document preview: S3 files proxied through the backend to avoid CORS issues

### User Experience
- Landing page with animated hero and interactive showcase
- Drag-and-drop file uploader with upload progress
- Dashboard with live stats: active jobs, storage used (GB), success rate
- Filterable, searchable, sortable document list with pagination
- Per-document detail view with real-time progress tracker and inline data editor
- CSV and per-document JSON export

### Scalability
- Stateless API and worker containers — horizontally scalable
- Neon PostgreSQL (serverless) with pgBouncer connection pooling
- GZip response compression middleware
- Configurable worker concurrency and queue depth limits

---

## Technology Stack

### Frontend

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Framework | React | 19.x | UI component framework |
| Language | TypeScript | 5.9.x | Type-safe development |
| Build Tool | Vite | 8.x | Fast dev server and production bundler |
| Styling | Tailwind CSS | 4.x | Utility-first CSS framework |
| Routing | React Router v7 | 7.x | SPA routing |
| Data Fetching | TanStack Query | 5.x | Server state management and caching |
| HTTP Client | Axios | 1.x | API communication with interceptors |
| Animation | Framer Motion | 12.x | Page and component animations |
| Authentication | Clerk React | 5.x | Auth UI components and token management |
| Forms | React Hook Form + Zod | 7.x / 4.x | Form state and schema validation |
| File Upload | React Dropzone | 15.x | Drag-and-drop file upload |
| Icons | Lucide React | latest | Icon library |
| Tables | TanStack Table | 8.x | Headless data table |
| Date Formatting | date-fns | 4.x | Date utilities |
| Deployment | Vercel | — | Static hosting with SPA rewrite rules |
| Production Server | Nginx | — | Static file serving in Docker |

### Backend

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Framework | FastAPI | 0.115.x | Async REST API and WebSocket server |
| ASGI Server | Uvicorn | 0.30.x | Production ASGI server (2 workers) |
| Language | Python | 3.11 | Backend runtime |
| ORM / Schema | Prisma (Python) | 0.15.x | Type-safe database access |
| Validation | Pydantic v2 | 2.10.x | Request/response validation |
| Authentication | Clerk Backend SDK | 1.7.x | JWT verification |
| Async HTTP | httpx | 0.27.x | Groq API calls from processors |
| PDF Parsing | PyPDF2 | 3.0.x | PDF text extraction |
| PDF to Image | pdf2image + poppler | 1.17.x | PDF → image for OCR fallback |
| OCR | Tesseract + pytesseract | — | Optical character recognition |
| DOCX | python-docx | 1.1.x | DOCX paragraph and table extraction |
| Image Processing | Pillow | 10.4.x | Image pre-processing before OCR |
| AWS SDK | boto3 | 1.35.x | S3 file upload/delete |
| File I/O | aiofiles | 24.x | Async local file write |
| Password Hashing | passlib (bcrypt) | — | Utility (available, not yet in auth flow) |
| Testing | Hypothesis + pytest-asyncio | — | Property-based and async testing |

### Queue & Worker

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Task Queue | Celery | 5.4.x | Distributed task processing |
| Message Broker | RabbitMQ | 3.12 | Task message delivery |
| Result Backend | Redis | 7.x | Task results and progress cache |
| Worker Pool | Prefork | — | 4 concurrent workers per container |
| Queue Monitor | Flower | 2.0 | Celery task dashboard (port 5555) |

### Database & Storage

| Component | Technology | Purpose |
|---|---|---|
| Database | PostgreSQL (Neon) | Primary data store (serverless) |
| Connection Pooling | pgBouncer (Neon built-in) | Manages connection limits across workers |
| ORM Client | Prisma Python (asyncio) | Generated type-safe DB client |
| File Storage | AWS S3 | Production document storage |
| Local Storage | Filesystem | Development document storage |
| Cache / Pub-Sub | Redis | Real-time progress, cancellation flags, active document tracking |

### Infrastructure & DevOps

| Component | Technology | Purpose |
|---|---|---|
| Containerization | Docker | Application packaging |
| Orchestration | Docker Compose | Multi-service local and production orchestration |
| Cloud Compute | AWS EC2 | Backend API + Worker hosting |
| Frontend Hosting | Vercel | Global CDN for React SPA |
| Database Hosting | Neon | Serverless PostgreSQL with auto-scaling to zero |
| CI/CD | GitHub Actions | Automated deployment on push to `main` |
| AI / LLM | Groq API | Summarization (`llama-3.1-8b-instant`) and Vision OCR (`llama-3.2-11b-vision-preview`) |

---

## System Architecture

### High-Level System Diagram

```mermaid
graph TB
    subgraph Client["Client Layer"]
        Browser["Browser\nReact 19 + TypeScript"]
    end

    subgraph Auth["Authentication"]
        Clerk["Clerk\nJWT Issuer"]
    end

    subgraph Frontend["Frontend Hosting"]
        Vercel["Vercel CDN\nNginx SPA"]
    end

    subgraph Backend["AWS EC2 — Docker Compose"]
        API["FastAPI\nUvicorn (2 workers)\nport 8000"]
        Worker["Celery Worker\nPrefork (4 concurrent)"]
        Scheduler["TaskScheduler\nRecovery Loop (20s)"]
        Flower["Flower Monitor\nport 5555"]
    end

    subgraph Queue["Message Queue"]
        RabbitMQ["RabbitMQ 3.12\nAMQP Broker\nManagement UI :15672"]
    end

    subgraph Cache["Cache & Pub/Sub"]
        Redis["Redis 7\nResult Backend\nProgress Store\nPub/Sub Bus"]
    end

    subgraph Database["Database"]
        Neon["Neon PostgreSQL\nServerless\npgBouncer Pooler"]
    end

    subgraph Storage["Object Storage"]
        S3["AWS S3\nDocument Files"]
    end

    subgraph AI["AI Services"]
        Groq["Groq API\nllama-3.1-8b-instant\nllama-3.2-11b-vision"]
    end

    Browser -->|"HTTPS REST + Bearer JWT"| API
    Browser -->|"WSS WebSocket"| API
    Browser -->|"Clerk SDK"| Clerk
    Clerk -->|"JWT Token"| Browser
    API -->|"Publish task"| RabbitMQ
    API -->|"Read/Write progress"| Redis
    API -->|"Prisma queries"| Neon
    API -->|"Upload/Delete/Proxy"| S3
    RabbitMQ -->|"Consume tasks"| Worker
    Worker -->|"Store results"| Neon
    Worker -->|"Publish progress events"| Redis
    Worker -->|"Download/read file"| S3
    Worker -->|"OCR + summarize"| Groq
    Redis -->|"Pub/Sub push"| API
    API -->|"WebSocket push"| Browser
    Scheduler -->|"Re-enqueue stuck docs"| RabbitMQ
    Scheduler -->|"Monitor active_documents set"| Redis
    Flower -->|"Inspect"| RabbitMQ
```

### Request Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant C as Clerk
    participant A as FastAPI
    participant S as AWS S3
    participant DB as Neon PostgreSQL
    participant Q as RabbitMQ
    participant W as Celery Worker
    participant R as Redis
    participant G as Groq API

    U->>C: Sign in
    C-->>U: JWT token
    U->>A: POST /api/v1/documents/upload (multipart + Bearer JWT)
    A->>A: Validate file type, size (≤50MB, ≤10 files)
    A->>S: Upload file to S3 bucket
    S-->>A: S3 URL
    A->>DB: Create Document (PENDING) + Job (PENDING)
    A->>DB: Update Document→QUEUED, Job→QUEUED
    A->>R: SADD active_documents {doc_id}
    A->>Q: celery.apply_async(process_document_task, task_id)
    A-->>U: DocumentListResponse (QUEUED)
    U->>A: WebSocket connect (?token=userId)
    U->>A: WS subscribe {jobId}
    Q->>W: Deliver task
    W->>DB: Update Document→PROCESSING, Job→PROCESSING
    W->>R: Publish progress:job_started (0%)
    R-->>A: Pub/Sub message
    A-->>U: WS progress event (0%)
    W->>S: Download file to temp path
    W->>W: Parse (PyPDF2/DOCX/Tesseract/Pillow)
    W->>R: Publish parsing_completed (40%)
    W->>W: Extract (title/category/summary/keywords)
    opt Groq Available
        W->>G: Summarize text
        G-->>W: AI summary
    end
    W->>R: Publish extraction_completed (90%)
    W->>DB: Create ProcessedData record
    W->>DB: Update Document→COMPLETED, Job→COMPLETED
    W->>R: Publish job_completed (100%)
    R-->>A: Pub/Sub message
    A-->>U: WS job_completed event
    U->>A: GET /api/v1/documents/{id}
    A->>DB: Fetch document + processedData
    A-->>U: Full DocumentResponse with extracted fields
```

### Job Processing State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING: Document created
    PENDING --> QUEUED: Celery task enqueued
    QUEUED --> PROCESSING: Worker picks up task
    PROCESSING --> COMPLETED: Extraction successful
    PROCESSING --> FAILED: Unhandled exception
    PROCESSING --> CANCELLED: Cancel flag in Redis
    QUEUED --> CANCELLED: Cancel requested
    FAILED --> QUEUED: Retry (≤3 attempts)
    CANCELLED --> QUEUED: Retry from scratch
    COMPLETED --> QUEUED: Re-process requested
    QUEUED --> QUEUED: Stuck recovery re-enqueue
    PROCESSING --> QUEUED: Stuck recovery re-enqueue
    COMPLETED --> [*]
```

---

## Detailed System Design

### Frontend Layer

The frontend is a React 19 single-page application written in TypeScript, built with Vite, and styled with Tailwind CSS v4.

**Routing:** React Router v7 with three authenticated routes (`/`, `/dashboard`, `/documents/:id`) and public routes (`/sign-in`, `/sign-up`). Unauthenticated users on `/` see the landing page; authenticated users are redirected to the upload view.

**Authentication:** Clerk React SDK handles sign-in, sign-up, session management, and JWT token retrieval. The `useApi` hook creates an Axios instance with a request interceptor that calls `getToken()` from Clerk and attaches the resulting Bearer JWT to every API request.

**Server State:** TanStack Query v5 manages all server state. Document lists poll every 3 seconds during active processing. `queryClient.invalidateQueries` is triggered on WebSocket `job_completed` and `job_failed` events to force an immediate data refresh.

**Real-Time Updates:** The `useWebSocket` hook establishes a WebSocket connection using the Clerk user ID as the token. It maintains a set of subscribed job IDs, sends `subscribe`/`unsubscribe` messages, and implements exponential backoff reconnection (up to 5 attempts, 1s–30s delay).

**Key Components:**
- `FileUploader`: Drag-and-drop multi-file uploader with upload progress tracking via Axios `onUploadProgress`
- `DocumentList`: Filterable, searchable document table with status badges and action buttons
- `DocumentDetail`: Full detail view with real-time `ProgressTracker` and inline `EditForm` for extracted data
- `DashboardPage`: Stats cards (active jobs, storage GB, success rate) computed from backend

**Build:** Vite's `manualChunks` splits React/React-DOM/React-Router into a `vendor` bundle. Static assets served with 1-year cache headers via Nginx or Vercel.

---

### Backend Layer

The backend is a FastAPI application served by Uvicorn with 2 workers, structured around versioned API routers under `/api/v1`.

**Startup/Shutdown (lifespan):** On startup, the app verifies Neon DB and S3 connectivity, connects the Redis client, starts the WebSocket Pub/Sub listener, and starts the `TaskScheduler`. On shutdown, it marks all in-flight documents as `FAILED`, purges the Celery queue, stops the scheduler, and closes all connections cleanly.

**Middleware:** CORS (`CORSMiddleware`) and GZip compression (`GZipMiddleware`, threshold 1 KB). Global exception handlers return consistent JSON error shapes.

**Authentication:** The `get_current_user_id` dependency reads the `HTTPBearer` token and returns the user ID. The architecture is prepared for full Clerk JWT verification (the Clerk Backend SDK is installed); the current implementation is simplified for the assessment context.

**Service Layer:** `DocumentService` orchestrates the full document lifecycle. It uses the `StorageService` abstraction (local or S3) for file I/O and calls `process_document_task.apply_async` to enqueue Celery tasks. The design cleanly separates HTTP concerns (API layer) from business logic (service layer).

**Storage Abstraction:** `StorageService` selects either `LocalStorageBackend` (dev) or `S3StorageBackend` (prod) based on the `STORAGE_TYPE` config value. S3 uploads run in a thread-pool executor to avoid blocking the async event loop.

---

### Database Layer

Neon PostgreSQL (serverless) accessed via the Prisma Python client (asyncio interface). The schema has four models: `User`, `Document`, `Job`, `ProcessedData`, plus a `ProgressEvent` audit log.

Connection pooling uses Neon's built-in pgBouncer pooler endpoint. The `DATABASE_URL` includes `pgbouncer=true` and `connection_limit` parameters that Prisma passes through. Each Celery task and each API request creates its own `Prisma()` instance, connects, performs its operations, and disconnects — avoiding connection leaks.

---

### Queue Layer

RabbitMQ serves as the AMQP message broker. Celery publishes one task per document: `app.workers.tasks.process_document_task(document_id, file_path)`. Key configuration decisions:

- `task_acks_late=True`: The task is acknowledged only after completion, not on delivery. If a worker crashes mid-task, the message is returned to the queue.
- `reject_on_worker_lost=True`: Combines with `acks_late` to requeue on worker death.
- `prefetch_multiplier=1`: Each worker fetches only one task at a time, enabling fair distribution across multiple worker containers.
- `worker_concurrency=4`: Up to 4 tasks processed concurrently per worker container (prefork).
- `max_tasks_per_child=100`: Workers are recycled after 100 tasks to prevent memory leaks from Tesseract/poppler processes.

---

### Cache & Pub/Sub Layer (Redis)

Redis serves three distinct roles:

1. **Celery Result Backend**: Stores task state and results (TTL: 1 hour).
2. **Progress Store**: A Redis hash `job:progress:{job_id}` holds the latest progress snapshot (status, message, %, timestamp). Used to deliver current status to WebSocket clients that connect mid-processing.
3. **Real-Time Pub/Sub**: Workers publish progress events to `progress:{job_id}` channels. The FastAPI WebSocket manager subscribes to `progress:*` (pattern subscribe) and pushes messages to connected browser clients.

Additional Redis keys:
- `job:cancel:{job_id}` — TTL flag set when a cancel is requested; checked by the worker at two checkpoints
- `active_documents` — a Redis Set of document IDs currently in `PENDING`/`QUEUED`/`PROCESSING` state, used by the scheduler to skip DB sweeps when idle (allowing Neon to scale to zero)

---

### Background Worker Layer

`process_document_task` is a Celery task running in a separate process. Each task:
1. Detects file type and instantiates the correct processor (`PDFProcessor`, `DOCXProcessor`, `ImageProcessor`, `TextProcessor`)
2. For S3 files: downloads to a local temp file, processes, then deletes the temp file in `finally`
3. Runs `parse()` (text extraction / OCR) then `extract_structured_data()` (title, category, summary, keywords)
4. Stores results as a `ProcessedData` record
5. Publishes progress events to Redis at each stage
6. All DB and Redis operations use `asyncio.wait_for` with timeouts to prevent indefinite hangs

---

### Scheduling Layer

`TaskScheduler` runs an async loop (`asyncio.sleep(20s)`) inside the FastAPI process. On each tick:
1. Checks the `active_documents` Redis Set. If empty, skips the DB query (saves Neon connection cost).
2. Calls `StuckDocumentRecovery.recover_stuck_documents()` which:
   - Fetches `PROCESSING`/`QUEUED` documents from DB whose IDs are in the Redis set
   - Calls Celery Inspect API to get currently running task IDs
   - Marks documents stuck longer than `SCHEDULER_STUCK_THRESHOLD` (default 300s) as recoverable
   - QUEUED documents with no active workers use a shorter threshold (30s)
   - Re-enqueues stuck documents with a fresh `task_id`

---

## Application Flow

### Single Document Upload and Processing

```
1.  User authenticates via Clerk (sign-in/sign-up).

2.  User drags files into the FileUploader component.
    → Axios POST /api/v1/documents/upload (multipart/form-data, Bearer JWT).

3.  FastAPI validates the request:
    → Max 10 files, max 50 MB per file.
    → Allowed types: PDF, DOCX, JPEG, PNG, TXT, CSV, HTML.
    → If batch (≥2 files): checks queue depth < 50.

4.  Files are uploaded to AWS S3 (or local storage in dev).
    → S3 URL returned as file_path.

5.  A DB transaction creates:
    → Document record (status: PENDING)
    → Job record (status: PENDING, placeholder celeryTaskId)

6.  For each document:
    → Job and Document updated to QUEUED.
    → document_id added to Redis active_documents set.
    → Celery task dispatched: process_document_task.apply_async(document_id, file_path, task_id=uuid)

7.  API returns DocumentListResponse to the browser.

8.  Browser opens WebSocket connection, sends subscribe {jobId}.

9.  Celery worker picks up the task from RabbitMQ:
    → Document + Job updated to PROCESSING.
    → Redis publishes job_started (0%).
    → Worker downloads file from S3 to a temp path.

10. Parser runs (stage 1 — 0–40%):
    → PDF: PyPDF2 text extraction; if sparse (<100 chars), falls back to Tesseract OCR;
            if Tesseract yields sparse text, falls back to Groq Vision API.
    → DOCX: python-docx paragraph + table extraction.
    → Image: Pillow preprocessing → Tesseract OCR.
    → Text: UTF-8 / latin-1 / cp1252 charset detection.
    → Redis publishes parsing_completed (40%).

11. Extractor runs (stage 2 — 40–90%):
    → Title: scored multi-candidate algorithm (top-30 lines).
    → Category: keyword signal scoring across 8 categories.
    → Summary: Groq LLM if GROQ_API_KEY set, else local TF-IDF extractive.
    → Keywords: TF-IDF-inspired scoring with capitalisation boost.
    → Redis publishes extraction_completed (90%).

12. Results stored:
    → ProcessedData record created in Neon PostgreSQL.
    → Document status → COMPLETED, Job status → COMPLETED.
    → Redis publishes job_completed (100%).
    → Temp file deleted, document_id removed from active_documents.

13. FastAPI WebSocket manager receives Pub/Sub event, pushes to browser.

14. Browser TanStack Query invalidates 'document' and 'documents' cache keys.

15. DocumentDetail page re-fetches and renders extracted data.

16. User can edit extracted fields, finalize, or export as JSON/CSV.
```

---

## Database Design

### Entity Descriptions

| Model | Description |
|---|---|
| `User` | Clerk-synced user record. `clerkId` is the unique identifier bridging Clerk's auth system to the application DB. |
| `Document` | Metadata about an uploaded file: name, type, size, storage path, and lifecycle status. One-to-one with `Job` and `ProcessedData`. |
| `Job` | Represents a single Celery task execution. Tracks `celeryTaskId`, status transitions, retry count, and timestamps. |
| `ProgressEvent` | Append-only audit log of all progress events emitted during a job execution. Stores eventType, message, and 0–100 progress integer. |
| `ProcessedData` | The output of the extraction pipeline: extracted text, title, category, summary, keywords array, JSON metadata, confidence score, review/finalization flags. |

### ERD

```mermaid
erDiagram
    User {
        string id PK
        string clerkId UK
        string email UK
        string firstName
        string lastName
        datetime createdAt
        datetime updatedAt
    }

    Document {
        string id PK
        string userId FK
        string filename
        string originalName
        string fileType
        int fileSize
        string filePath
        enum status
        datetime uploadedAt
        datetime updatedAt
    }

    Job {
        string id PK
        string documentId FK_UK
        string celeryTaskId UK
        enum status
        int retryCount
        int maxRetries
        datetime startedAt
        datetime completedAt
        datetime failedAt
        string errorMessage
        datetime createdAt
        datetime updatedAt
    }

    ProgressEvent {
        string id PK
        string jobId FK
        string eventType
        string message
        int progress
        json metadata
        datetime timestamp
    }

    ProcessedData {
        string id PK
        string documentId FK_UK
        string extractedText
        string title
        string category
        string summary
        string[] keywords
        json metadata
        float confidenceScore
        bool isReviewed
        bool isFinalized
        datetime reviewedAt
        datetime finalizedAt
        datetime createdAt
        datetime updatedAt
    }

    User ||--o{ Document : "owns"
    Document ||--o| Job : "has"
    Document ||--o| ProcessedData : "produces"
    Job ||--o{ ProgressEvent : "emits"
```

### Status Enums

**DocumentStatus:** `PENDING → QUEUED → PROCESSING → COMPLETED | FAILED | CANCELLED`

**JobStatus:** `PENDING | QUEUED | PROCESSING | COMPLETED | FAILED | CANCELLED | RETRYING`

### Indexes

| Table | Indexed Columns | Reason |
|---|---|---|
| User | `clerkId`, `email` | Auth lookup and uniqueness |
| Document | `userId`, `status`, `uploadedAt` | List queries and status filtering |
| Job | `celeryTaskId`, `status`, `createdAt` | Task lookup and monitoring |
| ProgressEvent | `jobId`, `timestamp` | Event log retrieval |
| ProcessedData | `documentId`, `isFinalized` | Direct lookup and export filtering |

---

## API Documentation

All endpoints are prefixed with `/api/v1`. Authentication is via `Authorization: Bearer <clerk_jwt>`.

### Documents

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/documents/upload` | Upload 1–10 files for processing |
| `GET` | `/documents` | List documents with filtering and pagination |
| `GET` | `/documents/stats/dashboard` | Get active jobs, storage used, success rate |
| `GET` | `/documents/{id}` | Get single document with extracted data |
| `DELETE` | `/documents/{id}` | Delete document (soft or permanent) |
| `GET` | `/documents/{id}/preview` | Stream/proxy file for browser preview |
| `PUT` | `/documents/{id}/processed-data` | Update extracted data fields |
| `POST` | `/documents/{id}/finalize` | Lock document from further edits |
| `POST` | `/documents/{id}/process` | Manually trigger processing on an uploaded doc |
| `POST` | `/documents/process-batch` | Trigger processing on multiple documents |
| `POST` | `/documents/{id}/cancel` | Cancel a queued or processing document |
| `POST` | `/documents/{id}/retry` | Retry a failed, cancelled, or completed document |

#### POST /documents/upload

```
Request:  multipart/form-data
  files[]     List[UploadFile]   Required. 1–10 files, max 50 MB each
  category    string             Optional. User-defined category label

Response: 200 DocumentListResponse
  {
    "documents": [
      {
        "id": "uuid",
        "filename": "abc123.pdf",
        "originalName": "contract.pdf",
        "fileType": "application/pdf",
        "fileSize": 204800,
        "filePath": "https://bucket.s3.region.amazonaws.com/uploads/abc123.pdf",
        "status": "QUEUED",
        "uploadedAt": "2024-01-01T00:00:00Z",
        "job": { "id": "uuid", "status": "QUEUED" }
      }
    ]
  }

Errors:
  400  Validation error (wrong type, too large, too many files)
  429  Queue depth exceeded (Retry-After: 60)
  500  Storage failure
```

#### GET /documents

```
Query Parameters:
  status    string   Filter by status (or comma-separated list)
  search    string   Case-insensitive search on originalName
  sort_by   string   Field to sort by (default: uploadedAt)
  order     string   asc | desc (default: desc)
  page      int      Page number (default: 1)
  limit     int      Items per page (default: 20)

Response: 200 DocumentListResponse with pagination metadata
  {
    "documents": [...],
    "pagination": { "total": 100, "page": 1, "limit": 20, "pages": 5 }
  }
```

#### POST /documents/{id}/cancel

```
Response: 200
  { "id": "uuid", "status": "CANCELLED", "message": "Document processing cancelled successfully" }

Errors:
  400  Document not in a cancellable state (not PROCESSING/QUEUED/PENDING)
  404  Document not found
```

#### POST /documents/{id}/retry

```
Response: 200
  { "id": "uuid", "status": "QUEUED", "job": {...}, "message": "Document queued for retry" }

Notes:
  - FAILED documents increment retryCount (max 3)
  - CANCELLED and COMPLETED documents restart from scratch
  - Returns 400 if retryCount >= maxRetries
  - Returns 400 if original file no longer exists
```

---

### Jobs

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/jobs/{id}/progress` | Get real-time progress (Redis-first, DB fallback) |
| `POST` | `/jobs/{id}/retry` | Retry a specific job |
| `POST` | `/jobs/{id}/cancel` | Set cancellation flag in Redis |

---

### Export

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/export/csv` | Download all finalized documents as CSV |
| `GET` | `/export/json` | Download specific documents as JSON |

```
Query Parameters (both):
  documentIds   string   Optional comma-separated list of document IDs

Response:
  CSV: attachment; filename=export.csv
  JSON: attachment; filename=export.json
       Fields: documentId, filename, status, title, category, summary, keywords, isFinalized
```

---

### Health

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | App health: version, Neon DB status, S3 status |
| `GET` | `/health/rabbitmq` | RabbitMQ broker health, active workers, queue names |
| `GET` | `/admin/cleanup-tasks` | Remove stale Celery tasks from queue |

---

### WebSocket

```
WS  /api/v1/ws?token={userId}

Client → Server messages:
  { "type": "subscribe",   "jobId": "uuid" }
  { "type": "unsubscribe", "jobId": "uuid" }
  { "type": "ping" }

Server → Client messages:
  {
    "type": "progress",
    "jobId": "uuid",
    "eventType": "parsing_started | parsing_completed | extraction_started | extraction_completed | job_completed | job_failed | job_cancelled",
    "message": "Parsing document",
    "progress": 40,
    "timestamp": 1704067200.0
  }
```

---

## Background Processing

### Component Roles

**RabbitMQ** acts as the durable AMQP message broker. When the API calls `process_document_task.apply_async(...)`, Celery serializes the task as a JSON message and publishes it to the default RabbitMQ queue. The message persists until a worker picks it up and acknowledges it. The management UI (`:15672`) provides queue depth, message rates, and consumer monitoring.

**Redis** serves as the Celery result backend (task state and return values, TTL 1 hour) and as the real-time communication bus. Workers write progress snapshots to Redis hashes and publish events to Redis Pub/Sub channels. FastAPI reads from both to serve REST polling and WebSocket push.

**Celery** orchestrates the worker process. The `process_document_task` is registered with `bind=True` (access to task context) and a custom `CallbackTask` base class that handles `on_failure` callbacks to mark documents as `FAILED` in the DB even when the task raises an unhandled exception.

### Task Execution Flow

```mermaid
flowchart TD
    A[API: apply_async] --> B[RabbitMQ Queue]
    B --> C{Worker Available?}
    C -->|Yes| D[Prefork Worker Process]
    C -->|No| B
    D --> E[Check cancel flag in Redis]
    E -->|Cancelled| F[Mark CANCELLED → exit]
    E -->|Continue| G[Parse document]
    G --> H{Parse success?}
    H -->|No text| I[Try Tesseract OCR]
    I --> J{OCR success?}
    J -->|Sparse text| K[Groq Vision API fallback]
    K --> L[Store Groq text]
    J -->|Success| L
    H -->|Text extracted| L
    L --> M[Check cancel flag]
    M -->|Cancelled| F
    M -->|Continue| N[Extract structured data]
    N --> O{Groq API key set?}
    O -->|Yes| P[Groq LLM summarize]
    O -->|No| Q[Local TF-IDF summary]
    P --> R[Store ProcessedData]
    Q --> R
    R --> S[Update Document+Job → COMPLETED]
    S --> T[Publish job_completed to Redis]
    T --> U[Delete temp file]
    U --> V[Disconnect DB + Redis]
```

### Retry Behavior

| Scenario | Behavior |
|---|---|
| Unhandled exception in task | `CallbackTask.on_failure` marks document FAILED; no Celery-level retry (max_retries=0) |
| User requests retry | API re-enqueues with fresh task_id; retryCount incremented for FAILED docs |
| Worker process killed mid-task | `task_acks_late` + `reject_on_worker_lost` returns message to RabbitMQ queue |
| Worker container crashes | RabbitMQ re-delivers unacknowledged task; `TaskScheduler` also detects after 300s |
| Queue purged on shutdown | `TaskScheduler` detects QUEUED/PROCESSING docs without active tasks and re-enqueues |

### Task Lifecycle Events

| Signal | Log Level | Trigger |
|---|---|---|
| `worker_ready` | INFO | Worker connected to RabbitMQ |
| `worker_shutdown` | INFO | Worker disconnecting |
| `before_task_publish` | INFO | Task enqueued to RabbitMQ |
| `task_prerun` | INFO | Worker acknowledges and starts task |
| `task_postrun` | INFO | Task completes successfully |
| `task_retry` | INFO | Task scheduled for retry |
| `task_rejected` | WARNING | Task rejected due to worker crash |

---

## Infrastructure Architecture

```mermaid
graph TB
    subgraph Internet
        User["End User\n(Browser)"]
    end

    subgraph VercelCDN["Vercel CDN (Global Edge)"]
        SPA["React SPA\nNginx / Vercel Edge\nHTTPS + SPA rewrites"]
    end

    subgraph EC2["AWS EC2 Instance\ndocker-compose.prod.yml"]
        direction TB
        NginxProxy["(Optional Nginx Reverse Proxy)\nport 80/443 → 8000"]
        
        subgraph DockerNetwork["Docker Bridge Network"]
            APIContainer["Backend Container\nFastAPI + Uvicorn\n2 workers, port 8000"]
            WorkerContainer["Celery Worker Container\nPrefork, 4 concurrent\nrestart: unless-stopped"]
            RabbitMQContainer["RabbitMQ Container\nport 5672 (AMQP)\nport 15672 (Management)\nrestart: unless-stopped"]
            FlowerContainer["Flower Container\nport 5555\nMonitoring UI"]
            StorageVolume["storage_data Volume\n/app/storage"]
        end
    end

    subgraph NeonCloud["Neon Cloud (Serverless)"]
        NeonDB["PostgreSQL 16\nAuto-scale to zero\npgBouncer Pooler endpoint\nDirect endpoint"]
    end

    subgraph RedisCloud["Redis (Docker / External)"]
        RedisNode["Redis 7\nCache + Pub/Sub + Results\nport 6379"]
    end

    subgraph AWSCloud["AWS"]
        S3Bucket["S3 Bucket\nDocument Files\nRegion: configurable"]
    end

    subgraph GroqCloud["Groq Cloud"]
        GroqAPI["Groq API\nllama-3.1-8b-instant\nllama-3.2-11b-vision-preview"]
    end

    subgraph GitHub["GitHub"]
        Repo["Repository\nmain branch"]
        Actions["GitHub Actions\ndeploy.yml"]
    end

    User -->|"HTTPS"| SPA
    User -->|"HTTPS REST + WSS"| NginxProxy
    NginxProxy --> APIContainer
    SPA -->|"HTTPS API calls"| APIContainer
    APIContainer -->|"AMQP publish"| RabbitMQContainer
    APIContainer -->|"Redis commands"| RedisNode
    APIContainer -->|"Prisma queries"| NeonDB
    APIContainer -->|"S3 put/delete/head"| S3Bucket
    RabbitMQContainer -->|"Task delivery"| WorkerContainer
    WorkerContainer -->|"Prisma updates"| NeonDB
    WorkerContainer -->|"Redis publish + set"| RedisNode
    WorkerContainer -->|"S3 download"| S3Bucket
    WorkerContainer -->|"HTTP POST"| GroqAPI
    RedisNode -->|"Pub/Sub"| APIContainer
    FlowerContainer -->|"Inspect"| RabbitMQContainer
    WorkerContainer --> StorageVolume
    APIContainer --> StorageVolume

    Repo -->|"git push main"| Actions
    Actions -->|"SSH + git reset + docker compose up"| EC2
```

### Deployment Topology Summary

| Component | Host | Access |
|---|---|---|
| React Frontend | Vercel (global CDN) | Public HTTPS |
| FastAPI Backend | AWS EC2 (Docker) | Public HTTPS (port 8000 or via reverse proxy) |
| Celery Worker | AWS EC2 (Docker, same compose) | Internal |
| RabbitMQ | AWS EC2 (Docker) | Internal (AMQP :5672), Management UI :15672 |
| Flower | AWS EC2 (Docker) | Internal / restricted :5555 |
| Redis | Docker (or external) | Internal :6379 |
| PostgreSQL | Neon Cloud | Serverless, auto-scaled |
| File Storage | AWS S3 | Private bucket, accessed via IAM credentials |

---

## CI/CD Pipeline

Deployment is fully automated via GitHub Actions on every push to `main`.

```mermaid
flowchart LR
    A[Developer\npushes to main] --> B[GitHub\nRepository]
    B --> C[GitHub Actions\ndeploy.yml triggered]
    C --> D[SSH into EC2\nappleboy/ssh-action@v1.0.3]
    D --> E[git fetch origin]
    E --> F[git reset --hard origin/main]
    F --> G[docker compose build]
    G --> H[docker compose up -d]
    H --> I[docker image prune -f]
    I --> J[Production\nRunning]
```

### Pipeline Details

| Step | Action |
|---|---|
| Trigger | `push` to `main` branch |
| Runner | `ubuntu-latest` (GitHub-hosted) |
| Authentication | `EC2_SSH_KEY` secret (private key), `EC2_HOST`, `EC2_USER` |
| Deploy | SSH action executes commands directly on EC2 |
| Git strategy | `git reset --hard origin/main` — ensures clean state, discards any local drifts |
| Build | `docker compose build` — rebuilds all changed images |
| Rollout | `docker compose up -d` — rolling replacement; healthy containers restart only if images changed |
| Cleanup | `docker image prune -f` — removes dangling images to conserve disk space |

### Required GitHub Secrets

| Secret | Purpose |
|---|---|
| `EC2_HOST` | EC2 instance public IP or hostname |
| `EC2_USER` | SSH username (e.g., `ubuntu`, `ec2-user`) |
| `EC2_SSH_KEY` | PEM private key for SSH authentication |

---

## Local Development Setup

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ and npm
- Python 3.11+
- Tesseract OCR (`brew install tesseract` on macOS)
- poppler (`brew install poppler` on macOS, required by pdf2image)

### 1. Clone the Repository

```bash
git clone https://github.com/<your-org>/Document-Text-Extractor.git
cd Document-Text-Extractor
```

### 2. Backend Environment Variables

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your values (see [Environment Variables](#environment-variables) section). At minimum:

```dotenv
DATABASE_URL="postgresql://user:pass@host/db?sslmode=require&pgbouncer=true&connection_limit=5"
CLERK_SECRET_KEY="sk_test_..."
STORAGE_TYPE="local"
LOCAL_STORAGE_PATH="./storage"
```

### 3. Frontend Environment Variables

```bash
cp frontend/.env.example frontend/.env
```

```dotenv
VITE_CLERK_PUBLISHABLE_KEY="pk_test_..."
VITE_API_URL="http://localhost:8000/api/v1"
VITE_WS_URL="ws://localhost:8000/api/v1/ws"
```

### 4. Start Infrastructure Services (Redis + RabbitMQ)

```bash
docker compose up redis rabbitmq -d
```

Wait for both to be healthy:

```bash
docker compose ps
```

### 5. Run the Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
prisma generate
prisma db push        # apply schema to your Neon DB
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Run the Celery Worker

In a separate terminal:

```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info --concurrency=4 --pool=prefork
```

### 7. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` (or `5174` if 5173 is in use).

### 8. Run with Docker Compose (Full Stack)

To run the entire stack in Docker:

```bash
docker compose up --build
```

Services:
| Service | URL |
|---|---|
| Frontend | `http://localhost:5174` (if included) |
| Backend API | `http://localhost:8000` |
| API Docs | `http://localhost:8000/docs` |
| RabbitMQ Management | `http://localhost:15672` (guest/guest) |
| Flower | `http://localhost:5555` |
| Redis | `localhost:6379` |

### 9. Run Tests

```bash
cd backend
pytest tests/ -v
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Purpose | Required | Default |
|---|---|---|---|
| `DEBUG` | Enable debug mode and auto-reload | No | `False` |
| `APP_NAME` | Application display name | No | `Document Processing API` |
| `FRONTEND_URL` | Frontend origin for CORS | No | `http://localhost:5174` |
| `CORS_ORIGINS` | Comma-separated allowed origins or JSON array | No | localhost variants |
| `DATABASE_URL` | Primary PostgreSQL connection string | **Yes** | — |
| `DATABASE_URL_POOLED` | Neon pgBouncer pooled connection URL | No | — |
| `DATABASE_URL_DIRECT` | Neon direct connection URL | No | — |
| `REDIS_URL` | Full Redis connection URL | No | built from host/port |
| `REDIS_HOST` | Redis hostname | No | `localhost` |
| `REDIS_PORT` | Redis port | No | `6379` |
| `REDIS_DB` | Redis database index | No | `0` |
| `REDIS_PASSWORD` | Redis password | No | — |
| `RABBITMQ_URL` | Full RabbitMQ AMQP URL | No | built from components |
| `RABBITMQ_HOST` | RabbitMQ hostname | No | `localhost` |
| `RABBITMQ_PORT` | RabbitMQ AMQP port | No | `5672` |
| `RABBITMQ_USER` | RabbitMQ username | No | `guest` |
| `RABBITMQ_PASSWORD` | RabbitMQ password | No | `guest` |
| `RABBITMQ_VHOST` | RabbitMQ virtual host | No | `/` |
| `CELERY_BROKER_URL` | Celery broker URL (overrides RabbitMQ build) | No | built |
| `CELERY_RESULT_BACKEND` | Celery result backend URL (overrides Redis build) | No | built |
| `CLERK_SECRET_KEY` | Clerk backend secret key for JWT verification | **Yes** | — |
| `CLERK_FRONTEND_API` | Clerk frontend API domain | No | — |
| `STORAGE_TYPE` | Storage backend: `local` or `s3` | No | `local` |
| `LOCAL_STORAGE_PATH` | Local storage directory | No | `./storage` |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key | If S3 | — |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key | If S3 | — |
| `AWS_S3_BUCKET` | S3 bucket name | If S3 | — |
| `AWS_REGION` | AWS region | No | `us-east-1` |
| `MAX_UPLOAD_SIZE` | Max file size in bytes | No | `52428800` (50 MB) |
| `MAX_FILES_PER_UPLOAD` | Max files per upload request | No | `10` |
| `TASK_TIMEOUT` | Celery task hard time limit (seconds) | No | `1800` (30 min) |
| `MAX_RETRIES` | Max document retry attempts | No | `3` |
| `PRISMA_POOL_TIMEOUT` | Prisma connection timeout (seconds) | No | `30` |
| `PRISMA_OPERATION_TIMEOUT` | Prisma query timeout (seconds) | No | `10` |
| `BATCH_UPLOAD_MAX_QUEUE_DEPTH` | Max docs in queue before 429 | No | `50` |
| `SCHEDULER_HEALTH_CHECK_INTERVAL` | Recovery sweep interval (seconds, 5–300) | No | `20` |
| `SCHEDULER_STUCK_THRESHOLD` | Age before doc considered stuck (seconds, ≥60) | No | `300` |
| `GROQ_API_KEY` | Groq API key for LLM summarization + Vision OCR | No | — |
| `GROQ_VISION_MAX_PAGES` | Max pages for Groq Vision fallback (0 = unlimited) | No | `10` |

### Frontend (`frontend/.env`)

| Variable | Purpose | Required | Default |
|---|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | Clerk publishable key for frontend SDK | **Yes** | — |
| `VITE_API_URL` | Backend API base URL | No | `http://localhost:8000/api/v1` |
| `VITE_WS_URL` | Backend WebSocket base URL | No | `ws://localhost:8000/api/v1/ws` |

### Root `.env` (for Docker Compose)

| Variable | Purpose |
|---|---|
| `RABBITMQ_USER` | RabbitMQ default username |
| `RABBITMQ_PASSWORD` | RabbitMQ default password |
| `RABBITMQ_VHOST` | RabbitMQ default virtual host |
| `CELERY_BROKER_URL` | Used by Flower service |

---

## Production Deployment Guide

### EC2 Prerequisites

1. Launch an EC2 instance (recommended: `t3.medium` or larger for OCR workloads).
2. Install Docker and Docker Compose:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
   sudo usermod -aG docker $USER
   ```
3. Open inbound ports: `22` (SSH), `8000` (API), `80`/`443` (optional reverse proxy).

### Initial Deployment

```bash
# On EC2
git clone https://github.com/<your-org>/Document-Text-Extractor.git ~/Document-Text-Extractor
cd ~/Document-Text-Extractor

# Create backend/.env with production values
cp backend/.env.example backend/.env
nano backend/.env   # Set DATABASE_URL, CLERK_SECRET_KEY, AWS_*, STORAGE_TYPE=s3, etc.

# Create root .env for Docker Compose
echo "RABBITMQ_USER=your_user" > .env
echo "RABBITMQ_PASSWORD=your_password" >> .env
echo "CELERY_BROKER_URL=amqp://your_user:your_password@rabbitmq:5672/" >> .env

# Build and launch
docker compose -f docker-compose.prod.yml up -d --build
```

### Prisma Migrations (First Time)

```bash
docker compose -f docker-compose.prod.yml exec backend prisma db push
```

### Automated Deployments (GitHub Actions)

Configure three repository secrets:
- `EC2_HOST`: Public IP or hostname of the EC2 instance
- `EC2_USER`: SSH user (e.g., `ubuntu`)
- `EC2_SSH_KEY`: Contents of the EC2 PEM private key

Every push to `main` will SSH into EC2, pull latest code, rebuild images, and redeploy.

### SSL / HTTPS (Recommended)

Install Nginx and Certbot on the EC2 host:

```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

Configure Nginx to proxy `/` to `localhost:8000` and terminate TLS. Update `CORS_ORIGINS` in `backend/.env` to include your production domain. Set `VITE_API_URL` and `VITE_WS_URL` in the Vercel frontend deployment to your production domain.

### Scaling Recommendations

**Vertical scaling:** Upgrade EC2 instance type for more CPU (OCR is CPU-bound). `t3.large` or `c5.xlarge` recommended for Tesseract-heavy workloads.

**Horizontal Worker Scaling:** Add more worker containers in `docker-compose.prod.yml`:
```yaml
worker2:
  extends:
    service: worker
```
Each worker adds 4 parallel processing slots.

**Neon Auto-scaling:** Neon PostgreSQL scales compute automatically. Use the pooled endpoint (`-pooler`) with `pgbouncer=true` in `DATABASE_URL` to handle concurrent connection bursts from multiple workers.

---

## Performance & Scalability

### Why Queues?

Synchronous document processing would block the HTTP request thread for the entire duration of OCR + extraction (up to 30 minutes per document). The RabbitMQ + Celery architecture decouples upload from processing:

- The API responds immediately (< 1 second) after storing the file and enqueuing the task.
- Workers process documents independently, without any connection to the HTTP request lifecycle.
- Failed tasks can be retried without re-uploading.
- Queue depth provides natural backpressure (HTTP 429 at configurable depth).

### Horizontal Scaling Opportunities

| Component | Scaling Method |
|---|---|
| FastAPI API | Increase `--workers` in Uvicorn, or add EC2 instances behind a load balancer |
| Celery Workers | Launch additional `worker` containers or EC2 instances; RabbitMQ distributes tasks evenly |
| Redis | Upgrade to Redis Cluster or a managed service (ElastiCache) for HA |
| RabbitMQ | Migrate to CloudAMQP or Amazon MQ for managed HA clustering |
| Neon DB | Neon auto-scales CPU/RAM; use read replicas for analytics queries |
| S3 | Inherently scalable; no changes needed |

### Worker Scaling

Each Celery worker uses `prefetch_multiplier=1`, meaning it only holds one task at a time before requesting the next. This makes it safe to run N worker containers — RabbitMQ distributes tasks across all consumers without any single worker hoarding the queue.

Adding a second worker container doubles effective throughput (from 4 to 8 concurrent OCR jobs).

### Database Connection Management

Neon PostgreSQL supports serverless auto-scaling but has per-plan connection limits. The application uses:
- Prisma Python (asyncio) with per-request/per-task connect/disconnect pattern
- pgBouncer pooler endpoint with `connection_limit=5` per Prisma client instance
- `BATCH_UPLOAD_MAX_QUEUE_DEPTH` guard prevents connection spikes from burst uploads
- `SCHEDULER_HEALTH_CHECK_INTERVAL` combined with Redis `active_documents` set skips DB sweeps when idle, allowing Neon's compute to scale to zero

### Storage Scalability

AWS S3 provides virtually unlimited storage capacity with 11 nines of durability. The `StorageService` abstraction allows swapping backends without changing business logic. For high-throughput uploads, S3 multipart uploads can be added to the `S3StorageBackend` class.

---

## Security Considerations

### Authentication

The application uses **Clerk** for authentication. The frontend obtains a short-lived JWT from Clerk and attaches it as a `Bearer` token on every API request. The backend's `get_current_user_id` dependency is designed to verify this JWT against Clerk's JWKS endpoint using the `clerk-backend-api` SDK.

> **Note:** The current implementation in `app/core/auth.py` uses a simplified mock verification suitable for the assessment context. In production, replace it with full Clerk JWT verification using the installed `clerk-backend-api` library.

### Document Access Control

All document queries include `userId` as a filter: `db.document.find_first(where={"id": document_id, "userId": user.id})`. This ensures users can only access their own documents. User records are identified by `clerkId`, which is the immutable Clerk user ID.

### Secrets Management

- All secrets are stored as environment variables, never hardcoded.
- AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) are loaded from environment only when `STORAGE_TYPE=s3`.
- Database credentials are in `backend/.env`, excluded from version control via `.gitignore`.
- Production secrets are injected via GitHub Actions repository secrets for CI/CD.
- Clerk secret keys follow the `sk_test_` / `sk_live_` prefix convention for environment separation.

### AWS S3 Access

- S3 files are uploaded as private objects (no public ACL).
- The backend proxies file preview requests through a `StreamingResponse`, avoiding direct public S3 URLs exposed to the browser. This prevents CORS issues and keeps files private.
- S3 deletion is performed server-side; clients never receive presigned delete URLs.
- Recommended: Apply an IAM policy scoped to the specific bucket with only `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, and `s3:HeadObject` permissions.

### Database Access

- Neon PostgreSQL enforces TLS by default (`sslmode=require`).
- Connection credentials are never logged; the startup S3 check logs only success/failure, not credentials.
- Connection strings with `@` characters are redacted in Celery startup logs: `settings.CELERY_BROKER_URL.split('@')[-1]`.

### Production Hardening Recommendations

1. **Enable full Clerk JWT verification** in `app/core/auth.py`.
2. **Restrict RabbitMQ Management UI** (`:15672`) to internal IPs only via security groups.
3. **Restrict Flower** (`:5555`) — add basic auth or place behind VPN.
4. **Set `DEBUG=False`** in production `backend/.env`.
5. **Use HTTPS** for all API and WebSocket traffic (Nginx + Let's Encrypt).
6. **Rotate credentials** — use AWS IAM roles instead of static access keys where possible.
7. **Add rate limiting** to the upload endpoint (e.g., via nginx `limit_req` or a FastAPI middleware).
8. **Enable RabbitMQ authentication** with a non-default username and password.
9. **Set a Redis password** via `REDIS_PASSWORD` when Redis is exposed outside Docker.
10. **Review CORS_ORIGINS** — restrict to your production frontend domain in production.

---

## Future Improvements

### Observability & Monitoring
- Integrate **Prometheus + Grafana** or **Datadog** for API latency, worker throughput, queue depth, and error rate dashboards.
- Add **Sentry** for exception tracking in both the FastAPI application and Celery workers.
- Replace ad-hoc logging with **structured JSON logs** (e.g., using `structlog`) for better log aggregation in CloudWatch or Loki.
- Add a `/metrics` endpoint (FastAPI + `prometheus-fastapi-instrumentator`).

### Autoscaling
- Migrate workers to **Kubernetes** with a **KEDA (Kubernetes Event-driven Autoscaling)** scaler triggered by RabbitMQ queue depth — automatically spin up workers under load.
- Use **AWS ECS Fargate** with SQS or AmazonMQ as a fully managed alternative.

### Authentication
- Complete **Clerk JWT verification** in `app/core/auth.py` using the installed SDK.
- Add **role-based access control** (admin role for the `/admin/cleanup-tasks` endpoint).
- Implement **API key authentication** for programmatic/service-to-service access.

### Multi-Region & High Availability
- Deploy backend workers in multiple AWS regions with RabbitMQ federation or Amazon MQ.
- Use **CloudFront** in front of the Vercel frontend for additional edge caching.
- Configure Neon **read replicas** for analytics and export queries to offload the primary.

### Storage & Processing Enhancements
- Add **S3 multipart upload** support for files approaching the 50 MB limit.
- Support additional file formats: XLSX, PPTX, HTML (already in allowed types but no dedicated processor).
- Implement **document deduplication** via content hash before uploading.
- Add **page-level processing** for large PDFs (chunked approach with partial results).

### Developer Experience
- Add **OpenAPI schema export** and auto-generate a TypeScript client from it.
- Add **end-to-end tests** with Playwright for the upload → processing → review flow.
- Add a **Makefile** with common commands (`make dev`, `make test`, `make deploy`).

### Security Enhancements
- Implement **virus scanning** (e.g., ClamAV) on uploaded files before processing.
- Add **file content validation** (verify file magic bytes match the declared MIME type).
- Implement **per-user storage quotas** enforced at the API layer.
- Add **audit logging** for all document operations (delete, finalize, export).

---

## Repository Structure

```
Document-Text-Extractor/
│
├── .github/
│   └── workflows/
│       └── deploy.yml              # GitHub Actions CI/CD — deploys to EC2 on push to main
│
├── .kiro/
│   └── specs/                      # Kiro AI spec files (requirements, design, tasks)
│       ├── automatic-task-scheduler/
│       ├── aws-s3-connection-fix/
│       ├── batch-upload-task-enqueue-fix/
│       ├── document-processing-controls/
│       ├── document-processing-deadlock-fix/
│       ├── rabbitmq-broker-migration/
│       └── task-cancellation-cleanup-fix/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── documents.py    # Document CRUD, upload, cancel, retry, preview endpoints
│   │   │       ├── export.py       # CSV and JSON export endpoints
│   │   │       ├── health.py       # RabbitMQ health check endpoint
│   │   │       ├── jobs.py         # Job retry, cancel, progress endpoints
│   │   │       └── websocket.py    # WebSocket endpoint for real-time progress
│   │   │
│   │   ├── core/
│   │   │   ├── auth.py             # Bearer JWT authentication dependency
│   │   │   ├── config.py           # Pydantic Settings — all env vars with validation
│   │   │   ├── security.py         # bcrypt password utilities (available for future use)
│   │   │   └── websocket_manager.py# WebSocket connection manager + Redis Pub/Sub listener
│   │   │
│   │   ├── models/
│   │   │   └── __init__.py         # (Prisma-generated models; no SQLAlchemy models)
│   │   │
│   │   ├── schemas/
│   │   │   ├── document.py         # Pydantic request/response schemas for documents
│   │   │   ├── job.py              # Job schema
│   │   │   └── progress.py         # Progress event schema
│   │   │
│   │   ├── services/
│   │   │   ├── celery_inspector.py # Celery Inspect API wrapper (get active tasks)
│   │   │   ├── document_service.py # Core document lifecycle orchestration
│   │   │   ├── export_service.py   # CSV and JSON export logic
│   │   │   ├── job_service.py      # Job progress and cancellation
│   │   │   ├── storage_service.py  # Storage abstraction (local + S3 backends)
│   │   │   ├── stuck_document_recovery.py # Stuck document detection and re-enqueue
│   │   │   └── task_scheduler.py   # Background recovery loop (asyncio task)
│   │   │
│   │   ├── utils/
│   │   │   ├── celery_utils.py     # Stale task cleanup utility
│   │   │   ├── db_pool.py          # Prisma client factory + connect/disconnect helpers
│   │   │   ├── exceptions.py       # Custom exception classes
│   │   │   ├── file_utils.py       # File utility helpers
│   │   │   └── redis_client.py     # Long-lived FastAPI RedisClient + short-lived TaskRedisClient
│   │   │
│   │   ├── workers/
│   │   │   ├── celery_app.py       # Celery app config, signal handlers, startup logging
│   │   │   ├── tasks.py            # process_document_task — main processing logic
│   │   │   └── processors/
│   │   │       ├── base_processor.py   # Shared NLP: title, category, summary, keywords
│   │   │       ├── pdf_processor.py    # PyPDF2 + Tesseract OCR + Groq Vision fallback
│   │   │       ├── docx_processor.py   # python-docx paragraph + table extraction
│   │   │       ├── image_processor.py  # Pillow preprocessing + Tesseract OCR
│   │   │       └── text_processor.py   # Multi-encoding text file reader
│   │   │
│   │   └── main.py                 # FastAPI app factory, middleware, lifespan, router registration
│   │
│   ├── prisma/
│   │   └── schema.prisma           # Database schema: User, Document, Job, ProgressEvent, ProcessedData
│   │
│   ├── tests/                      # pytest + Hypothesis property-based tests
│   ├── .env.example                # All backend environment variables documented
│   ├── Dockerfile                  # Python 3.11-slim + Tesseract + poppler
│   ├── requirements.txt            # Python dependencies (pinned versions)
│   └── start.sh                    # Entrypoint: starts Celery worker + Uvicorn in one container
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── dashboard/          # DocumentList, SearchBar, StatusFilter, ActionButtons
│   │   │   ├── detail/             # DocumentDetail, EditForm, ProgressTracker
│   │   │   ├── landing/            # InteractiveShowcase (landing page demo)
│   │   │   └── upload/             # FileUploader (drag-and-drop, multi-file)
│   │   │
│   │   ├── hooks/
│   │   │   ├── useApi.ts           # Axios instance factory with Clerk JWT interceptor
│   │   │   ├── useDocuments.ts     # TanStack Query hooks for document list and detail
│   │   │   └── useWebSocket.ts     # WebSocket hook with subscription management + reconnect
│   │   │
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx   # Stats cards + document table + export button
│   │   │   ├── DocumentDetailPage.tsx # Detail view with progress tracker
│   │   │   └── UploadPage.tsx      # Upload form + success state
│   │   │
│   │   ├── services/
│   │   │   ├── documentService.ts  # All document API calls
│   │   │   └── exportService.ts    # CSV and JSON download triggers
│   │   │
│   │   └── App.tsx                 # Router, nav, Clerk auth guards, landing page
│   │
│   ├── .env.example                # Frontend environment variables
│   ├── Dockerfile                  # Node build → Nginx serve
│   ├── nginx.conf                  # SPA routing + asset caching
│   ├── vercel.json                 # Vercel SPA rewrite rules
│   ├── package.json                # Dependencies (React 19, Vite 8, TanStack, Clerk)
│   └── vite.config.ts              # Build config: React plugin, Tailwind, API proxy, chunking
│
├── docker-compose.yml              # Development stack: Redis, RabbitMQ, backend, worker, flower
├── docker-compose.prod.yml         # Production stack: RabbitMQ, backend, worker, frontend
├── .env                            # Root-level env for Docker Compose variables
├── .gitignore
└── README.md                       # This file
```

---

## Acknowledgments

Built on the shoulders of:
- [FastAPI](https://fastapi.tiangolo.com/) — the backbone async Python web framework
- [Celery](https://docs.celeryq.dev/) — distributed task queue
- [Prisma](https://prisma.io/) — next-gen ORM with type-safe Python client
- [Neon](https://neon.tech/) — serverless PostgreSQL
- [Clerk](https://clerk.com/) — authentication and user management
- [Groq](https://groq.com/) — ultra-fast LLM inference
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — open-source OCR engine
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) — modern frontend toolchain
