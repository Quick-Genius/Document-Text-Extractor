from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_user_id
from app.services.job_service import JobService

router = APIRouter()

@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, user_id: str = Depends(get_current_user_id)):
    job_service = JobService()
    await job_service.retry_job(job_id)
    return {"message": "Job retry initiated"}

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user_id: str = Depends(get_current_user_id)):
    job_service = JobService()
    await job_service.cancel_job(job_id)
    return {"message": "Job cancellation initiated"}

@router.get("/jobs/{job_id}/progress")
async def get_job_progress(job_id: str, user_id: str = Depends(get_current_user_id)):
    job_service = JobService()
    progress = await job_service.get_job_progress(job_id)
    return progress
