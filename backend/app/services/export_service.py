from app.core.config import settings
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
import csv
import io
import json
from datetime import datetime


def get_prisma():
    from prisma import Prisma
    return Prisma()


def _serialize(obj):
    """JSON-serialise Prisma model objects."""
    if hasattr(obj, '__dict__'):
        return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    return obj


class ExportService:
    def __init__(self):
        pass

    async def export_json(self, user_id: str, document_ids: Optional[str] = None) -> StreamingResponse:
        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                return JSONResponse(content=[])

            where_clause = {"userId": user.id, "processedData": {"isNot": None}}
            if document_ids:
                ids_list = document_ids.split(",")
                where_clause["id"] = {"in": ids_list}
                
            documents = await db.document.find_many(
                where=where_clause,
                include={"processedData": True}
            )
        finally:
            await db.disconnect()
            
        data = [_serialize(doc) for doc in documents]
        
        json_str = json.dumps(data, indent=2)
        output = io.BytesIO(json_str.encode('utf-8'))
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=export.json"},
        )

    async def export_csv(self, user_id: str, document_ids: Optional[str] = None) -> StreamingResponse:
        db = get_prisma()
        await db.connect()
        try:
            user = await db.user.find_unique(where={"clerkId": user_id})
            if not user:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["documentId", "filename", "status", "title", "category", "summary", "keywords", "isFinalized"])
                output.seek(0)
                return StreamingResponse(
                    iter([output.getvalue()]),
                    media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=export.csv"},
                )

            where_clause = {"userId": user.id, "processedData": {"isNot": None}}
            if document_ids:
                ids_list = document_ids.split(",")
                where_clause["id"] = {"in": ids_list}
                
            documents = await db.document.find_many(
                where=where_clause,
                include={"processedData": True}
            )
        finally:
            await db.disconnect()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["documentId", "filename", "status", "title", "category", "summary", "keywords", "isFinalized"])

        for doc in documents:
            pd = doc.processedData
            writer.writerow([
                doc.id,
                doc.originalName,
                doc.status,
                pd.title if pd else "",
                pd.category if pd else "",
                pd.summary if pd else "",
                ";".join(pd.keywords) if pd and pd.keywords else "",
                pd.isFinalized if pd else False,
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"},
        )
