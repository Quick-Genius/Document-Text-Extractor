from fastapi import APIRouter
from .api.v1 import documents, jobs, websocket, export

api_router = APIRouter()
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
