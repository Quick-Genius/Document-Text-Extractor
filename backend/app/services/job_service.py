# from prisma import Prisma
from app.core.config import settings
from app.utils.redis_client import redis_client
from app.utils.exceptions import NotFoundError
import logging

logger = logging.getLogger(__name__)

class JobService:
    def __init__(self):
        # self.db = Prisma(datasource={"db": {"url": settings.DATABASE_URL}})
        pass

    async def retry_job(self, job_id: str):
        """
        Retry a failed or cancelled job - mocked
        """
        # Mock implementation
        pass

    async def cancel_job(self, job_id: str):
        """
        Set cancellation flag in Redis for the worker to pick up
        """
        await redis_client.set(f"job:cancel:{job_id}", "1", ex=3600)
        logger.info(f"Cancellation flag set for job {job_id}")

    async def get_job_progress(self, job_id: str):
        """
        Get current job progress from Redis (real-time) or DB (fallback)
        """
        # Check Redis first for real-time progress
        progress_data = await redis_client.hgetall(f"job:progress:{job_id}")
        if progress_data:
            return progress_data
        
        # Fallback to DB
        await self.db.connect()
        try:
            job = await self.db.job.find_unique(
                where={"id": job_id},
                include={"progressEvents": True}
            )
            if not job:
                raise NotFoundError("Job not found")
            
            # Sort events in memory since Prisma Python find_unique include doesn't support order_by yet in all versions
            sorted_events = sorted(job.progressEvents, key=lambda x: x.timestamp, reverse=True)
            
            if sorted_events:
                event = sorted_events[0]
                return {
                    "status": job.status,
                    "progress": str(event.progress),
                    "message": event.message,
                    "updated_at": event.timestamp.isoformat()
                }
            
            return {
                "status": job.status,
                "progress": "0",
                "message": "Waiting to start...",
                "updated_at": job.updatedAt.isoformat()
            }
        finally:
            await self.db.disconnect()
