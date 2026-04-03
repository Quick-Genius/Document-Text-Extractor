from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.core.auth import get_current_user_id
from app.services.export_service import ExportService

router = APIRouter()

@router.get("/export/json")
async def export_json(documentIds: Optional[str] = Query(None), user_id: str = Depends(get_current_user_id)):
    export_service = ExportService()
    return await export_service.export_json(user_id, documentIds)

@router.get("/export/csv")
async def export_csv(documentIds: Optional[str] = Query(None), user_id: str = Depends(get_current_user_id)):
    export_service = ExportService()
    return await export_service.export_csv(user_id, documentIds)
