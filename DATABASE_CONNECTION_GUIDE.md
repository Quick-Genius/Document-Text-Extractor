# Database & Storage Connection Guide

## ✅ Connection Status

- **Neon DB**: ✓ Connected successfully using direct URL
- **AWS S3**: ✓ Ready (currently using local storage, but S3 configured)

## Neon DB Connection Types

Neon PostgreSQL provides **two connection URL types**, each optimized for different workloads:

### 1. **Pooled Connection (Recommended for Serverless/FastAPI)**
- Uses pgBouncer connection pooling
- Hostname contains `-pooler` suffix
- **Recommended for**: Serverless functions, frequent short connections, scalable APIs
- **Format**:
  ```
  postgresql://user:password@ep-xxxxx-pooler.region.aws.neon.tech/dbname?sslmode=require
  ```
- **Note**: Do NOT use `channel_binding=require` with pooled connections

### 2. **Direct Connection (Recommended for Long-Running Processes)**
- Direct PostgreSQL connection without pooling
- Regular hostname (no `-pooler`)
- **Recommended for**: Traditional servers, Celery workers, batch jobs
- **Format**:
  ```
  postgresql://user:password@ep-xxxxx.region.aws.neon.tech/dbname?sslmode=require&channel_binding=require
  ```

## Configuration

### Environment Variables in `.env`

```env
# Main database URL (used by Prisma)
DATABASE_URL="postgresql://neondb_owner:npg_BTaZ5vtS3sOL@ep-jolly-art-a1dzpkfp.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Optional: Explicit pooled URL (uncomment to override DATABASE_URL)
# DATABASE_URL_POOLED="postgresql://neondb_owner:npg_BTaZ5vtS3sOL@ep-jolly-art-a1dzpkfp-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# Optional: Explicit direct URL (uncomment to override DATABASE_URL)
# DATABASE_URL_DIRECT="postgresql://neondb_owner:npg_BTaZ5vtS3sOL@ep-jolly-art-a1dzpkfp.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
```

### How Neon URL Selection Works

1. **Primary**: Uses `DATABASE_URL` if no overrides are set
2. **Priority Order** (if multiple are set):
   - `DATABASE_URL_POOLED` (if set, used for serverless/APIs)
   - `DATABASE_URL_DIRECT` (if set, used for workers/batch jobs)
   - Falls back to `DATABASE_URL`

### When to Switch Connection Types

**Use Pooled** (`-pooler`) for:
- FastAPI/Uvicorn servers (our primary use case)
- Frequent short-lived connections
- Serverless functions
- Any scalable web service

**Use Direct** for:
- Celery workers (long-running background tasks)
- Batch processing jobs
- Services requiring `channel_binding`

### Example: Switching to Pooled URL

Edit `.env` and uncomment the pooled URL:

```env
DATABASE_URL_POOLED="postgresql://neondb_owner:npg_BTaZ5vtS3sOL@ep-jolly-art-a1dzpkfp-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
```

The application will automatically use the pooled connection.

## AWS S3 Configuration

### Current Status
- **STORAGE_TYPE**: `local` (uses local filesystem at `./storage`)
- **AWS_ACCESS_KEY_ID**: ✓ Configured
- **AWS_SECRET_ACCESS_KEY**: ✓ Configured
- **AWS_S3_BUCKET**: `assesmentbucket74408`

### To Enable S3 Storage

Edit `.env` and change:

```env
STORAGE_TYPE=s3
```

The application will automatically:
1. Use AWS S3 instead of local storage
2. Validate S3 connectivity on startup
3. Upload documents to S3 bucket instead of local filesystem

## Connection Verification

### Test Neon DB Connection

```bash
cd backend
python << 'EOF'
from pathlib import Path
from dotenv import load_dotenv
import os
import psycopg2

load_dotenv(Path('.env'))
db_url = os.getenv('DATABASE_URL')

try:
    conn = psycopg2.connect(db_url, connect_timeout=10)
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
    conn.close()
    print('✓ Neon DB: Connected')
except Exception as e:
    print(f'✗ Neon DB: {e}')
EOF
```

### Test AWS S3 Connection

```bash
cd backend
python << 'EOF'
from pathlib import Path
from dotenv import load_dotenv
import os
import boto3

load_dotenv(Path('.env'))

try:
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name="us-east-1"
    )
    s3.head_bucket(Bucket="assesmentbucket74408")
    print('✓ AWS S3: Connected')
except Exception as e:
    print(f'✗ AWS S3: {e}')
EOF
```

### Check Health Endpoint

```bash
# Start the backend
cd backend
uvicorn app.main:app --port 8000 --reload

# In another terminal
curl http://localhost:8000/health | python -m json.tool
```

Expected response (with local storage):
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "neon_connected": true,
    "s3_connected": false
}
```

## Environment Variable Loading

The application automatically loads `.env` at startup using `python-dotenv`:

1. **Config module** (`app/core/config.py`): Loads `.env` when imported
2. **Connection checks**: Use the loaded environment variables
3. **Prisma**: Uses the loaded `DATABASE_URL` environment variable

### For Celery Workers

Celery workers inherit environment variables from the parent shell. To ensure .env is loaded:

```bash
cd backend
set -a  # Export all variables
source .env
set +a  # Reset export behavior

# Now start Celery worker
REDIS_URL=$REDIS_URL celery -A app.workers.celery_app worker --loglevel=info
```

Or simpler approach:

```bash
cd backend
eval $(grep -v '^#' .env | xargs)
REDIS_URL=$REDIS_URL celery -A app.workers.celery_app worker --loglevel=info
```

## Recent Changes

### Fixed Issues

1. **Added python-dotenv**: Ensures `.env` file is loaded at application startup
2. **Improved Neon health check**: Uses `psycopg2` directly instead of Prisma for faster/more reliable checks
3. **Added Neon URL flexibility**: Supports pooled and direct URLs via environment variable overrides
4. **Better error logging**: Health checks provide detailed error messages for diagnostics

### Added Packages

```
python-dotenv>=1.0.0      # Load .env files
psycopg2-binary==2.9.9    # Direct PostgreSQL connections for health checks
```

## Troubleshooting

### "Unable to locate credentials" (AWS)

**Cause**: Environment variables not loaded into the process
**Fix**: 
```bash
# Source .env before starting
set -a && source .env && set +a
# Then start the app
uvicorn app.main:app --port 8000
```

### Neon Connection Timeout

**Cause**: Using wrong connection type or pooler URL unavailable
**Fix**:
1. Verify you're using the correct URL format
2. Check if `-pooler` is in the hostname
3. Try switching between pooled/direct URLs

### "No database configured" Error

**Cause**: `DATABASE_URL` environment variable not set
**Fix**:
```bash
python -c "from pathlib import Path; from dotenv import load_dotenv; load_dotenv(Path('.env')); import os; print('DB:', os.getenv('DATABASE_URL'))"
```

## Summary

✅ **Neon DB Connection**: Working with direct URL (optimal for Celery workers)
✅ **AWS S3 Configuration**: Ready for production (switch `STORAGE_TYPE=s3`)
✅ **Environment Loading**: Automatic via `python-dotenv`
✅ **Health Checks**: Reliable async checks in startup lifecycle
