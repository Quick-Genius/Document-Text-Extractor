"""
Bug Condition Exploration Test for Document Processing Deadlock Fix

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**

This test explores the bug condition where batch uploads of 2+ documents
cause deadlocks and concurrency issues. 

CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

The test encodes the expected behavior - it will validate the fix when it passes
after implementation.

GOAL: Surface counterexamples that demonstrate:
- Documents remain in PENDING status after timeout
- Connection pool exhaustion errors
- Redis singleton deadlock errors
- Lost job status updates
- Worker threads blocked indefinitely
"""

import pytest
import asyncio
import time
import os
import tempfile
from io import BytesIO
from hypothesis import given, strategies as st, settings, HealthCheck
from fastapi import UploadFile
from app.services.document_service import DocumentService
from app.workers.tasks import process_document_task
from prisma import Prisma
import logging

logger = logging.getLogger(__name__)

# Test configuration
BATCH_UPLOAD_TIMEOUT = 120  # 2 minutes - documents should complete within this time
PROCESSING_CHECK_INTERVAL = 5  # Check status every 5 seconds
MAX_WAIT_ITERATIONS = BATCH_UPLOAD_TIMEOUT // PROCESSING_CHECK_INTERVAL


def create_test_file(filename: str, content: str = "Test document content") -> UploadFile:
    """Create a test file for upload"""
    file_content = content.encode('utf-8')
    file = BytesIO(file_content)
    
    # Determine content type based on extension
    if filename.endswith('.pdf'):
        content_type = 'application/pdf'
    elif filename.endswith('.docx'):
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif filename.endswith('.txt'):
        content_type = 'text/plain'
    else:
        content_type = 'application/octet-stream'
    
    return UploadFile(
        filename=filename,
        file=file,
        size=len(file_content),
        headers={'content-type': content_type}
    )


async def wait_for_documents_completion(db: Prisma, document_ids: list[str], timeout: int = BATCH_UPLOAD_TIMEOUT) -> dict:
    """
    Wait for all documents to complete processing and collect diagnostic information.
    
    Returns dict with:
    - all_completed: bool
    - statuses: dict of document_id -> status
    - elapsed_time: float
    - stuck_in_pending: list of document_ids
    - errors: list of error messages
    """
    start_time = time.time()
    result = {
        'all_completed': False,
        'statuses': {},
        'elapsed_time': 0,
        'stuck_in_pending': [],
        'errors': []
    }
    
    for iteration in range(MAX_WAIT_ITERATIONS):
        elapsed = time.time() - start_time
        
        # Check status of all documents
        documents = await db.document.find_many(
            where={'id': {'in': document_ids}},
            include={'job': True}
        )
        
        statuses = {doc.id: doc.status for doc in documents}
        result['statuses'] = statuses
        result['elapsed_time'] = elapsed
        
        # Check if all completed
        completed_statuses = {'COMPLETED', 'FAILED', 'CANCELLED'}
        all_done = all(status in completed_statuses for status in statuses.values())
        
        if all_done:
            result['all_completed'] = True
            # Check for failures
            for doc in documents:
                if doc.status == 'FAILED' and doc.job and doc.job.errorMessage:
                    result['errors'].append(f"Document {doc.id}: {doc.job.errorMessage}")
            return result
        
        # Log progress
        pending_count = sum(1 for s in statuses.values() if s == 'PENDING')
        processing_count = sum(1 for s in statuses.values() if s == 'PROCESSING')
        completed_count = sum(1 for s in statuses.values() if s == 'COMPLETED')
        logger.info(f"Iteration {iteration + 1}/{MAX_WAIT_ITERATIONS}: "
                   f"PENDING={pending_count}, PROCESSING={processing_count}, COMPLETED={completed_count}, "
                   f"elapsed={elapsed:.1f}s")
        
        await asyncio.sleep(PROCESSING_CHECK_INTERVAL)
    
    # Timeout reached - collect diagnostic info
    result['elapsed_time'] = time.time() - start_time
    result['stuck_in_pending'] = [doc_id for doc_id, status in result['statuses'].items() 
                                   if status == 'PENDING']
    
    # Collect error information from jobs
    for doc_id in document_ids:
        doc = await db.document.find_unique(
            where={'id': doc_id},
            include={'job': True}
        )
        if doc and doc.job and doc.job.errorMessage:
            result['errors'].append(f"Document {doc_id}: {doc.job.errorMessage}")
    
    return result


@pytest.mark.asyncio
@given(
    batch_size=st.integers(min_value=2, max_value=3),
    file_type=st.sampled_from(['txt'])
)
@settings(
    max_examples=1,  # Reduced for faster execution
    deadline=None,  # Disable deadline for long-running tests
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_batch_upload_deadlock_bug_condition(batch_size: int, file_type: str):
    """
    Property 1: Bug Condition - Batch Upload Deadlock and Concurrency Issues
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**
    
    This test verifies that batch uploads of 2+ documents complete successfully
    with proper:
    - Transaction isolation (1.1)
    - Connection pooling (1.2)
    - Database locking (1.3)
    - Task-scoped Redis clients (1.4)
    - Task coordination (1.5)
    - Checkpoint validation (1.6)
    - Operation timeouts (1.7)
    - Rate limiting (1.8)
    
    EXPECTED OUTCOME ON UNFIXED CODE: FAIL
    - Documents remain in PENDING status after 5 minutes
    - Connection pool exhaustion errors in logs
    - Redis singleton deadlock errors
    - Lost job status updates
    - Worker threads blocked indefinitely
    
    EXPECTED OUTCOME ON FIXED CODE: PASS
    - All documents complete processing successfully
    - No deadlocks or connection exhaustion
    - Proper concurrency controls in place
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing batch upload: {batch_size} documents of type {file_type}")
    logger.info(f"{'='*80}")
    
    # Setup
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_user_{int(time.time() * 1000)}"
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
        files = []
        for i in range(batch_size):
            filename = f"test_doc_{i}.{file_type}"
            content = f"Test document {i} content for batch upload testing. " * 10
            files.append(create_test_file(filename, content))
        
        # Execute batch upload
        service = DocumentService()
        logger.info(f"Uploading batch of {batch_size} documents...")
        upload_start = time.time()
        
        documents = await service.create_documents_from_upload(
            user_id=test_user_id,
            files=files
        )
        
        upload_time = time.time() - upload_start
        logger.info(f"Batch upload completed in {upload_time:.2f}s, created {len(documents)} documents")
        
        document_ids = [doc.id for doc in documents]
        
        # Wait for processing to complete
        logger.info(f"Waiting for {len(document_ids)} documents to complete processing...")
        result = await wait_for_documents_completion(db, document_ids)
        
        # Log results
        logger.info(f"\n{'='*80}")
        logger.info(f"BATCH UPLOAD TEST RESULTS")
        logger.info(f"{'='*80}")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"File type: {file_type}")
        logger.info(f"All completed: {result['all_completed']}")
        logger.info(f"Elapsed time: {result['elapsed_time']:.1f}s")
        logger.info(f"Final statuses: {result['statuses']}")
        
        if result['stuck_in_pending']:
            logger.error(f"Documents stuck in PENDING: {result['stuck_in_pending']}")
        
        if result['errors']:
            logger.error(f"Errors encountered:")
            for error in result['errors']:
                logger.error(f"  - {error}")
        
        logger.info(f"{'='*80}\n")
        
        # Assertions - these will FAIL on unfixed code
        assert result['all_completed'], (
            f"DEADLOCK DETECTED: Not all documents completed within {BATCH_UPLOAD_TIMEOUT}s. "
            f"Stuck in PENDING: {result['stuck_in_pending']}. "
            f"This confirms the bug exists. "
            f"Possible causes: "
            f"1. Transaction isolation missing (1.1) - race conditions in batch creation "
            f"2. Connection pool exhaustion (1.2) - no connection pooling configured "
            f"3. Database locking missing (1.3) - lost job status updates "
            f"4. Redis singleton deadlock (1.4) - shared connection across tasks "
            f"5. No task coordination (1.5) - uncontrolled concurrent execution "
            f"6. No checkpoint validation (1.6) - tasks hung indefinitely "
            f"7. No operation timeouts (1.7) - database operations blocking "
            f"8. No rate limiting (1.8) - system overload"
        )
        
        # Verify no documents failed
        failed_docs = [doc_id for doc_id, status in result['statuses'].items() 
                      if status == 'FAILED']
        assert not failed_docs, (
            f"Documents failed during processing: {failed_docs}. "
            f"Errors: {result['errors']}"
        )
        
        # Verify all documents completed successfully
        completed_docs = [doc_id for doc_id, status in result['statuses'].items() 
                         if status == 'COMPLETED']
        assert len(completed_docs) == batch_size, (
            f"Expected {batch_size} completed documents, got {len(completed_docs)}. "
            f"Statuses: {result['statuses']}"
        )
        
        logger.info(f"✓ Batch upload of {batch_size} documents completed successfully")
        
    finally:
        # Cleanup
        try:
            # Delete test documents
            await db.document.delete_many(
                where={'userId': user.id}
            )
            # Delete test user
            await db.user.delete(
                where={'id': user.id}
            )
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


@pytest.mark.asyncio
async def test_simple_batch_upload_deadlock():
    """
    Simple test case for batch upload deadlock (no property-based testing)
    
    This test uploads 3 documents simultaneously and verifies they all complete.
    
    EXPECTED OUTCOME ON UNFIXED CODE: FAIL - documents stuck in PENDING
    EXPECTED OUTCOME ON FIXED CODE: PASS - all documents complete
    """
    batch_size = 3
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Simple batch upload test: {batch_size} documents")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_simple_{int(time.time() * 1000)}"
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
        files = [create_test_file(f"simple_test_{i}.txt", f"Content {i} " * 20) 
                for i in range(batch_size)]
        
        # Execute batch upload
        service = DocumentService()
        documents = await service.create_documents_from_upload(
            user_id=test_user_id,
            files=files
        )
        
        document_ids = [doc.id for doc in documents]
        logger.info(f"Created {len(document_ids)} documents, waiting for completion...")
        
        # Wait for processing
        result = await wait_for_documents_completion(db, document_ids, timeout=120)
        
        # Log results
        logger.info(f"All completed: {result['all_completed']}")
        logger.info(f"Elapsed time: {result['elapsed_time']:.1f}s")
        logger.info(f"Final statuses: {result['statuses']}")
        
        if result['stuck_in_pending']:
            logger.error(f"Documents stuck in PENDING: {result['stuck_in_pending']}")
        
        # Assertions
        assert result['all_completed'], (
            f"DEADLOCK DETECTED: Documents did not complete within 120s. "
            f"Stuck in PENDING: {result['stuck_in_pending']}. "
            f"This confirms the batch upload deadlock bug exists."
        )
        
        logger.info(f"✓ Simple batch upload test passed")
        
    finally:
        # Cleanup
        try:
            await db.document.delete_many(where={'userId': user.id})
            await db.user.delete(where={'id': user.id})
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


@pytest.mark.asyncio
async def test_batch_upload_connection_pool_exhaustion():
    """
    Specific test for connection pool exhaustion (Requirement 1.2)
    
    This test uploads enough documents to exhaust the default connection pool
    and verifies the system handles it gracefully.
    
    EXPECTED OUTCOME ON UNFIXED CODE: FAIL with connection pool errors
    EXPECTED OUTCOME ON FIXED CODE: PASS with connection pooling
    """
    batch_size = 15  # More than typical default pool size of 10
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing connection pool exhaustion with {batch_size} documents")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_pool_{int(time.time() * 1000)}"
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
        files = [create_test_file(f"pool_test_{i}.txt", f"Content {i}") 
                for i in range(batch_size)]
        
        # Execute batch upload
        service = DocumentService()
        documents = await service.create_documents_from_upload(
            user_id=test_user_id,
            files=files
        )
        
        document_ids = [doc.id for doc in documents]
        
        # Wait for processing
        result = await wait_for_documents_completion(db, document_ids)
        
        # Check for connection pool errors
        connection_errors = [err for err in result['errors'] 
                           if 'connection' in err.lower() or 'pool' in err.lower()]
        
        if connection_errors:
            logger.error(f"Connection pool errors detected: {connection_errors}")
        
        # Assertions
        assert result['all_completed'], (
            f"Connection pool exhaustion detected: documents did not complete. "
            f"This confirms bug 1.2 (no connection pooling). "
            f"Errors: {result['errors']}"
        )
        
        logger.info(f"✓ Connection pool test passed with {batch_size} documents")
        
    finally:
        # Cleanup
        try:
            await db.document.delete_many(where={'userId': user.id})
            await db.user.delete(where={'id': user.id})
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--log-cli-level=INFO"])
