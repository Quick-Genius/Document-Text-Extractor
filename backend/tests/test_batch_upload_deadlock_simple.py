"""
Simplified Bug Condition Exploration Test for Document Processing Deadlock Fix

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**

This test demonstrates the batch upload deadlock bug with a simple, fast test case.

CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.

EXPECTED COUNTEREXAMPLES:
- Documents remain in PENDING status after timeout
- Connection pool exhaustion errors
- Redis connection errors (Broken pipe)
- PostgreSQL connection errors
- Only some documents complete, others stuck
"""

import pytest
import asyncio
import time
from io import BytesIO
from fastapi import UploadFile
from app.services.document_service import DocumentService
from prisma import Prisma
import logging

logger = logging.getLogger(__name__)

# Reduced timeout for faster test execution
TIMEOUT = 60  # 1 minute
CHECK_INTERVAL = 3  # Check every 3 seconds


def create_test_file(filename: str, content: str = "Test content") -> UploadFile:
    """Create a test file for upload"""
    file_content = content.encode('utf-8')
    file = BytesIO(file_content)
    
    return UploadFile(
        filename=filename,
        file=file,
        size=len(file_content),
        headers={'content-type': 'text/plain'}
    )


@pytest.mark.asyncio
async def test_batch_upload_deadlock_simple():
    """
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**
    
    Simple test that uploads 3 documents and verifies they all complete.
    
    EXPECTED ON UNFIXED CODE: FAIL
    - Documents stuck in PENDING
    - Redis connection errors
    - PostgreSQL connection errors
    - Worker threads blocked
    
    EXPECTED ON FIXED CODE: PASS
    - All documents complete successfully
    - No connection errors
    - Proper concurrency controls
    """
    batch_size = 3
    
    logger.info(f"\n{'='*80}")
    logger.info(f"BATCH UPLOAD DEADLOCK TEST - {batch_size} documents")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_deadlock_{int(time.time() * 1000)}"
        user = await db.user.upsert(
            where={'clerkId': test_user_id},
            data={
                'create': {
                    'clerkId': test_user_id,
                    'email': f'{test_user_id}@test.com'
                },
                'update': {}
            }
        )
        
        # Create batch of test files
        files = [create_test_file(f"doc_{i}.txt", f"Test content {i} " * 50) 
                for i in range(batch_size)]
        
        # Execute batch upload
        service = DocumentService()
        logger.info(f"Uploading {batch_size} documents...")
        
        documents = await service.create_documents_from_upload(
            user_id=test_user_id,
            files=files
        )
        
        document_ids = [doc.id for doc in documents]
        logger.info(f"Created {len(document_ids)} documents")
        
        # Wait for completion with timeout
        start_time = time.time()
        max_iterations = TIMEOUT // CHECK_INTERVAL
        
        for iteration in range(max_iterations):
            elapsed = time.time() - start_time
            
            # Check document statuses
            docs = await db.document.find_many(
                where={'id': {'in': document_ids}},
                include={'job': True}
            )
            
            statuses = {doc.id: doc.status for doc in docs}
            pending = sum(1 for s in statuses.values() if s == 'PENDING')
            processing = sum(1 for s in statuses.values() if s == 'PROCESSING')
            completed = sum(1 for s in statuses.values() if s == 'COMPLETED')
            failed = sum(1 for s in statuses.values() if s == 'FAILED')
            
            logger.info(f"[{elapsed:.1f}s] PENDING={pending}, PROCESSING={processing}, "
                       f"COMPLETED={completed}, FAILED={failed}")
            
            # Check if all done
            if pending == 0 and processing == 0:
                logger.info(f"All documents completed in {elapsed:.1f}s")
                break
            
            await asyncio.sleep(CHECK_INTERVAL)
        else:
            # Timeout reached
            elapsed = time.time() - start_time
            logger.error(f"\n{'='*80}")
            logger.error(f"DEADLOCK DETECTED AFTER {elapsed:.1f}s")
            logger.error(f"{'='*80}")
            
            # Get final statuses
            docs = await db.document.find_many(
                where={'id': {'in': document_ids}},
                include={'job': True}
            )
            
            stuck_docs = []
            errors = []
            
            for doc in docs:
                logger.error(f"Document {doc.id[:8]}: status={doc.status}")
                if doc.status in ['PENDING', 'PROCESSING']:
                    stuck_docs.append(doc.id)
                if doc.job and doc.job.errorMessage:
                    errors.append(f"{doc.id[:8]}: {doc.job.errorMessage}")
            
            if errors:
                logger.error(f"\nErrors found:")
                for error in errors:
                    logger.error(f"  - {error}")
            
            logger.error(f"\nCOUNTEREXAMPLES FOUND:")
            logger.error(f"  - {len(stuck_docs)} documents stuck in PENDING/PROCESSING")
            logger.error(f"  - Check Celery worker logs for:")
            logger.error(f"    * Redis connection errors (Broken pipe)")
            logger.error(f"    * PostgreSQL connection errors")
            logger.error(f"    * Connection pool exhaustion")
            logger.error(f"{'='*80}\n")
            
            # This assertion will FAIL on unfixed code (which is expected!)
            pytest.fail(
                f"DEADLOCK CONFIRMED: {len(stuck_docs)}/{batch_size} documents stuck after {elapsed:.1f}s. "
                f"This proves the bug exists. "
                f"Root causes: "
                f"(1.1) No transaction isolation, "
                f"(1.2) No connection pooling, "
                f"(1.3) No database locking, "
                f"(1.4) Redis singleton deadlock, "
                f"(1.5) No task coordination, "
                f"(1.6) No checkpoint validation, "
                f"(1.7) No operation timeouts, "
                f"(1.8) No rate limiting"
            )
        
        # Verify all completed successfully
        final_docs = await db.document.find_many(
            where={'id': {'in': document_ids}}
        )
        
        completed_count = sum(1 for doc in final_docs if doc.status == 'COMPLETED')
        failed_count = sum(1 for doc in final_docs if doc.status == 'FAILED')
        
        assert completed_count == batch_size, (
            f"Expected {batch_size} completed, got {completed_count}"
        )
        assert failed_count == 0, f"Found {failed_count} failed documents"
        
        logger.info(f"✓ Test PASSED - all {batch_size} documents completed successfully")
        
    finally:
        # Cleanup
        try:
            await db.document.delete_many(where={'userId': user.id})
            await db.user.delete(where={'id': user.id})
            logger.info("Cleanup completed")
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--log-cli-level=INFO"])
