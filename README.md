# Document Processing System

AI-powered document processing pipeline. Upload PDFs, DOCX, images, and text files — the system extracts structured data, generates summaries, and provides real-time processing status.

## Stack

- **Frontend**: React + TypeScript + Vite (Clerk auth)
- **Backend**: FastAPI + Celery workers
- **Queue**: RabbitMQ
- **Database**: PostgreSQL (Neon)
- **Cache/PubSub**: Redis
- **Storage**: AWS S3 (or local)
- **AI**: Groq (LLaMA), Google Gemini

## Local Development

### Prerequisites
- Docker + Docker Compose
- Node 20+
- Python 3.11+

### Setup

```bash
# 1. Clone and configure
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Fill in your credentials in both .env files

# 2. Start all services
docker-compose up -d

# 3. Frontend is at http://localhost:5173
# 4. Backend API is at http://localhost:8000
# 5. RabbitMQ UI is at http://localhost:15672 (guest/guest)
# 6. Celery Flower is at http://localhost:5555
```

## Production Deployment

### Option 1: Railway (recommended)

1. Push to GitHub
2. Create a new Railway project → Deploy from GitHub
3. Add 3 services: `backend`, `worker`, `rabbitmq`
4. Set environment variables from `backend/.env.example`
5. Deploy frontend to Vercel: `cd frontend && vercel`

### Option 2: Docker Compose on a VPS

```bash
# On your server
git clone <repo>
cp backend/.env.example backend/.env
# Fill in production credentials

docker-compose -f docker-compose.prod.yml up -d
```

The production compose file:
- Removes dev bind mounts (code is baked into the image)
- Runs uvicorn with 2 workers (no `--reload`)
- Builds frontend with nginx serving the static bundle
- Sets `restart: unless-stopped` on all services

### Environment Variables

See `backend/.env.example` for all required variables. Key ones for production:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `REDIS_URL` | Redis Cloud connection string |
| `RABBITMQ_URL` | CloudAMQP or self-hosted RabbitMQ |
| `CLERK_SECRET_KEY` | Clerk backend API key |
| `AWS_ACCESS_KEY_ID` | S3 access key |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key |
| `AWS_S3_BUCKET` | S3 bucket name |
| `GROQ_API_KEY` | Groq API key for AI summarization |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |

## Architecture

```
Browser → Frontend (React)
              ↓ REST/WebSocket
         Backend (FastAPI)
              ↓ Enqueue
         RabbitMQ
              ↓ Consume
         Celery Worker
              ↓ Store results
         PostgreSQL (Neon)
              ↓ Pub/Sub events
         Redis → WebSocket → Browser
```
