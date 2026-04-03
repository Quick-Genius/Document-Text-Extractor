from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class JobBase(BaseModel):
    status: str
    retryCount: int
    maxRetries: int
    errorMessage: Optional[str]

class JobCreate(JobBase):
    pass

class JobResponse(JobBase):
    id: str
    celeryTaskId: str
    startedAt: Optional[datetime]
    completedAt: Optional[datetime]
    failedAt: Optional[datetime]

    class Config:
        from_attributes = True
