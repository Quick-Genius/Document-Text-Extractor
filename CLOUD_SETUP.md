# Cloud Services Setup Guide

## 1. Neon DB (PostgreSQL)

### Setup Steps:
1. Go to [neon.tech](https://neon.tech) and sign up for a free account
2. Create a new project
3. Copy the connection string from the dashboard
4. Update your `.env` file:

```env
DATABASE_URL="postgresql://username:password@hostname/database?sslmode=require"
```

**Free Tier**: 512MB storage, 100 hours compute time/month

## 2. Redis Cloud (Redis)

### Option A: Redis Cloud (Recommended)
1. Go to [redis.com](https://redis.com) and sign up
2. Create a free database (30MB)
3. Get your connection details
4. Update `.env`:

```env
REDIS_URL="redis://username:password@hostname:port"
# OR individual settings:
REDIS_HOST="hostname"
REDIS_PORT=port
REDIS_PASSWORD="password"
```

### Option B: Upstash Redis (Alternative)
1. Go to [upstash.com](https://upstash.com) and sign up
2. Create a Redis database
3. Copy the connection details
4. Use the same `.env` format as above

**Free Tier**: Redis Cloud offers 30MB, Upstash offers 10,000 requests/month

## 3. AWS S3 (File Storage)

### Setup Steps:
1. Go to [aws.amazon.com](https://aws.amazon.com) and create a free account
2. Go to IAM and create a new user with S3 permissions
3. Create an S3 bucket
4. Get your access keys
5. Update `.env`:

```env
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID="your_access_key"
AWS_SECRET_ACCESS_KEY="your_secret_key"
AWS_S3_BUCKET="your_bucket_name"
AWS_REGION="us-east-1"
```

**Free Tier**: 5GB storage, 20,000 GET requests, 2,000 PUT requests/month

## Alternative Free Storage Options:

### Cloudflare R2 (Completely Free)
1. Go to [dash.cloudflare.com](https://dash.cloudflare.com)
2. Navigate to R2
3. Create a bucket
4. Get API tokens

### Supabase Storage (Free Tier)
1. Go to [supabase.com](https://supabase.com)
2. Create a project
3. Use Storage section
4. Get connection details

## Complete .env Template:

```env
# Database (Neon)
DATABASE_URL="postgresql://username:password@hostname/database?sslmode=require"

# Redis (Redis Cloud/Upstash)
REDIS_URL="redis://username:password@hostname:port"

# AWS S3
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID="your_access_key"
AWS_SECRET_ACCESS_KEY="your_secret_key"
AWS_S3_BUCKET="your_bucket_name"
AWS_REGION="us-east-1"

# Other settings...
DEBUG=True
APP_NAME="Document Processing API"
FRONTEND_URL="http://localhost:5173"
CORS_ORIGINS="http://localhost:5173,http://localhost:3000"
CLERK_SECRET_KEY=sk_test_...
MAX_UPLOAD_SIZE=52428800
MAX_FILES_PER_UPLOAD=10
TASK_TIMEOUT=1800
MAX_RETRIES=3
```

## Testing the Setup:

After configuring all services, restart your backend:

```bash
cd backend
source venv/bin/activate
python app/main.py
```

The application will now use cloud services instead of local ones.</content>
<parameter name="filePath">/Users/sky_walker/Documents/Assesments /Predusk Technology pvt ltd/CLOUD_SETUP.md