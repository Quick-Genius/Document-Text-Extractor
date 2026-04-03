from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProgressEventBase(BaseModel):
    eventType: str
    message: str
    progress: int
    metadata: Optional[dict]

class ProgressEventCreate(ProgressEventBase):
    pass

class ProgressEventResponse(ProgressEventBase):
    id: str
    timestamp: datetime

    class Config:
        from_attributes = True
