import asyncio
from app.services.document_service import DocumentService
from app.core.config import settings

async def main():
    service = DocumentService()
    # Need to get a document ID first
    db = getattr(service, 'get_prisma', lambda: None)()
    if not db:
        from prisma import Prisma
        db = Prisma()
    await db.connect()
    
    doc = await db.document.find_first()
    if not doc:
        print("No document found")
        return
        
    print(f"Found document {doc.id} with filePath {doc.filePath}, user {doc.userId}")
    
    # Try soft delete
    try:
        await service.delete_document(doc.id, doc.user.clerkId if doc.user else "user_2g", False)
        print("Soft delete succeeded!")
    except Exception as e:
        print(f"Soft delete failed: {e}")
        
    await db.disconnect()

asyncio.run(main())
