from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.api.v1 import documents, jobs, export, websocket, health
from app.utils.redis_client import redis_client
from app.core.websocket_manager import websocket_manager
from app.services.task_scheduler import TaskScheduler
from app.utils.db_pool import get_prisma_with_pool
from app.workers.celery_app import celery_app

import boto3
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_neon_db() -> bool:
    """Check Neon DB connectivity using psycopg2"""
    try:
        import psycopg2
        from psycopg2 import sql
        
        # Parse the DATABASE_URL
        db_url = settings.DATABASE_URL
        
        # Connect with timeout
        conn = psycopg2.connect(db_url, connect_timeout=10)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        
        logger.info(f"Neon DB connection successful (using {'pooled' if '-pooler' in db_url else 'direct'} URL)")
        return True
    except psycopg2.OperationalError as e:
        logger.warning(f"Neon DB operational error: {e}")
        return False
    except ImportError:
        logger.warning("psycopg2 not installed; Neon DB connectivity check skipped")
        return False
    except Exception as e:
        logger.warning(f"Neon DB connection check failed: {type(e).__name__}: {e}")
        return False


async def check_aws_s3() -> bool:
    """Check AWS S3 connectivity"""
    if settings.STORAGE_TYPE.lower() != "s3":
        logger.info("Storage type is not S3; skipping S3 connectivity check")
        return False

    try:
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            logger.warning("AWS credentials not configured; S3 connectivity check skipped")
            return False

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        s3.head_bucket(Bucket=settings.AWS_S3_BUCKET)
        logger.info("AWS S3 connection successful")
        return True
    except (ClientError, BotoCoreError) as e:
        logger.warning(f"AWS S3 connectivity check failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"AWS S3 check failed: {type(e).__name__}: {e}")
        return False


async def _shutdown_cleanup(db):
    """
    On shutdown: mark all PROCESSING/QUEUED documents as FAILED
    and purge the Celery queue so nothing is left dangling.
    """
    try:
        from datetime import datetime

        # Find all in-flight documents
        stuck = await db.document.find_many(
            where={"status": {"in": ["PROCESSING", "QUEUED"]}},
            include={"job": True}
        )

        if stuck:
            logger.info(f"Shutdown cleanup: marking {len(stuck)} in-flight documents as FAILED")
            for doc in stuck:
                try:
                    await db.document.update(
                        where={"id": doc.id},
                        data={"status": "FAILED"}
                    )
                    if doc.job:
                        await db.job.update(
                            where={"id": doc.job.id},
                            data={
                                "status": "FAILED",
                                "failedAt": datetime.now(),
                                "errorMessage": "Backend instance stopped"
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to mark document {doc.id} as FAILED: {e}")
        else:
            logger.info("Shutdown cleanup: no in-flight documents found")

        # Purge the Celery queue so stale tasks don't run when the worker restarts
        try:
            celery_app.control.purge()
            logger.info("Shutdown cleanup: Celery queue purged")
        except Exception as e:
            logger.warning(f"Failed to purge Celery queue: {e}")

    except Exception as e:
        logger.error(f"Shutdown cleanup failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting application...")

    neon_ok = await check_neon_db()
    s3_ok = await check_aws_s3()

    app.state.neon_connected = neon_ok
    app.state.s3_connected = s3_ok

    if neon_ok:
        logger.info("Neon DB connected successfully")
    else:
        logger.warning("Neon DB connection failed")

    if s3_ok:
        logger.info("AWS S3 connected successfully")
    else:
        logger.warning("AWS S3 connection failed")

    await redis_client.connect()
    await websocket_manager.start()   # ← start Redis pub/sub listener
    
    # Initialize and start task scheduler
    db = get_prisma_with_pool()
    await db.connect()
    
    scheduler = TaskScheduler(
        db=db,
        celery_app=celery_app,
        health_check_interval=settings.SCHEDULER_HEALTH_CHECK_INTERVAL,
        max_concurrency=settings.SCHEDULER_MAX_CONCURRENCY
    )
    await scheduler.start()
    logger.info("Task scheduler started")
    
    # Store scheduler in app state for access by services
    app.state.scheduler = scheduler
    
    yield

    # Shutdown — mark in-flight documents as failed and clear the queue
    logger.info("Shutting down application...")
    await _shutdown_cleanup(db)
    await scheduler.stop()
    logger.info("Task scheduler stopped")
    await db.disconnect()
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

# API routers
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "neon_connected": getattr(app.state, "neon_connected", False),
        "s3_connected": getattr(app.state, "s3_connected", False),
    }


@app.get("/api/v1/admin/cleanup-tasks")
async def cleanup_stale_tasks():
    """
    Admin endpoint to cleanup stale Celery tasks
    
    This removes tasks from the queue that are:
    - Not in the database
    - Already completed/cancelled/failed in database
    """
    from app.utils.celery_utils import cleanup_stale_tasks as cleanup_fn
    from app.utils.db_pool import get_prisma_with_pool
    
    db = get_prisma_with_pool()
    await db.connect()
    
    try:
        stats = await cleanup_fn(db)
        return {
            "status": "success",
            "message": "Cleanup completed",
            "stats": stats
        }
    finally:
        await db.disconnect()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
