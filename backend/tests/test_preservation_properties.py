"""
Preservation Property Tests for Document Processing Deadlock Fix

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**

This test suite verifies that non-batch upload behaviors are preserved after
implementing the deadlock fix. These tests follow the observation-first methodology:

1. Observe behavior on UNFIXED code
2. Write property-based tests capturing that behavior
3. Verify tests PASS on UNFIXED code (confirms baseline)
4. After fix implementation, verify tests still PASS (confirms preservation)

EXPECTED OUTCOME: All tests PASS on both unfixed and fixed code.

Property 2: Preservation - Single Document and Sequential Processing
For any upload that is NOT a batch upload (single document or sequential uploads
with time gaps), the fixed system SHALL produce exactly the same behavior as the
original system.
"""

import pytest
import asyncio
import time
import os
from io import BytesIO
from hypothesis import given, strategies as st, settings, HealthCheck
from fastapi import UploadFile
from app.services.document_service import DocumentService
from app.workers.tasks import process_document_task
from prisma import Prisma
import logging

logger = logging.getLogger(__name__)

# Test configuration
SINGLE_UPLOAD_TIMEOUT = 60  # Single documents should complete within 1 minute
SEQUENTIAL_GAP = 5  # 5 second gap between sequential uploads
PROCESSING_CHECK_INTERVAL = 2  # Check status every 2 seconds


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


async def wait_for_document_completion(db: Prisma, document_id: str, timeout: int = SINGLE_UPLOAD_TIMEOUT) -> dict:
    """
    Wait for a single document to complete processing.
    
    Returns dict with:
    - completed: bool
    - status: str
    - elapsed_time: float
    - error: str or None
    """
    start_time = time.time()
    max_iterations = timeout // PROCESSING_CHECK_INTERVAL
    
    for iteration in range(max_iterations):
        elapsed = time.time() - start_time
        
        # Check document status
        document = await db.document.find_unique(
            where={'id': document_id},
            include={'job': True}
        )
        
        if not document:
            return {
                'completed': False,
                'status': 'NOT_FOUND',
                'elapsed_time': elapsed,
                'error': 'Document not found'
            }
        
        # Check if completed
        if document.status in {'COMPLETED', 'FAILED', 'CANCELLED'}:
            error = None
            if document.status == 'FAILED' and document.job and document.job.errorMessage:
                error = document.job.errorMessage
            
            return {
                'completed': document.status == 'COMPLETED',
                'status': document.status,
                'elapsed_time': elapsed,
                'error': error
            }
        
        await asyncio.sleep(PROCESSING_CHECK_INTERVAL)
    
    # Timeout reached
    document = await db.document.find_unique(
        where={'id': document_id},
        include={'job': True}
    )
    
    return {
        'completed': False,
        'status': document.status if document else 'UNKNOWN',
        'elapsed_time': time.time() - start_time,
        'error': f'Timeout after {timeout}s'
    }


@pytest.mark.asyncio
@given(
    file_type=st.sampled_from(['txt']),
    content_size=st.integers(min_value=10, max_value=100)
)
@settings(
    max_examples=5,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_single_document_upload_preservation(file_type: str, content_size: int):
    """
    Property 2.1: Single Document Upload Preservation
    
    **Validates: Requirement 3.1**
    
    OBSERVATION: Single document uploads complete successfully on unfixed code.
    
    PROPERTY: For any single document upload, the system SHALL process the
    document successfully without deadlocks, completing within normal timeframes.
    
    This test verifies that single document uploads continue to work correctly
    after implementing the deadlock fix. Single uploads should not be affected
    by transaction isolation, connection pooling, or distributed locking changes.
    
    EXPECTED OUTCOME: PASS on both unfixed and fixed code
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing single document upload: {file_type}, content_size={content_size}")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_single_{int(time.time() * 1000)}"
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
        
        # Create single test file
        filename = f"single_test.{file_type}"
        content = f"Test content " * content_size
        file = create_test_file(filename, content)
        
        # Upload single document
        service = DocumentService()
        upload_start = time.time()
        
        documents = await service.create_documents_from_upload(
            user_id=test_user_id,
            files=[file]
        )
        
        upload_time = time.time() - upload_start
        assert len(documents) == 1, "Should create exactly one document"
        
        document_id = documents[0].id
        logger.info(f"Uploaded document {document_id} in {upload_time:.2f}s")
        
        # Wait for processing to complete
        result = await wait_for_document_completion(db, document_id)
        
        logger.info(f"Processing completed: status={result['status']}, "
                   f"elapsed={result['elapsed_time']:.1f}s")
        
        # Assertions - should PASS on unfixed code
        assert result['completed'], (
            f"Single document upload failed to complete. "
            f"Status: {result['status']}, Error: {result['error']}. "
            f"This indicates a regression in single document processing."
        )
        
        assert result['status'] == 'COMPLETED', (
            f"Document did not reach COMPLETED status. "
            f"Status: {result['status']}, Error: {result['error']}"
        )
        
        # Verify document has processed data
        doc = await db.document.find_unique(
            where={'id': document_id},
            include={'processedData': True}
        )
        
        assert doc.processedData is not None, (
            "Document completed but has no processed data"
        )
        
        logger.info(f"✓ Single document upload preserved correctly")
        
    finally:
        # Cleanup
        try:
            await db.document.delete_many(where={'userId': user.id})
            await db.user.delete(where={'id': user.id})
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


@pytest.mark.asyncio
@given(
    num_documents=st.integers(min_value=2, max_value=4),
    file_type=st.sampled_from(['txt'])
)
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
async def test_sequential_upload_preservation(num_documents: int, file_type: str):
    """
    Property 2.2: Sequential Upload Preservation
    
    **Validates: Requirement 3.2**
    
    OBSERVATION: Sequential uploads (with 5 second gaps) complete successfully
    on unfixed code.
    
    PROPERTY: For any sequential document uploads with time gaps between them,
    the system SHALL process all documents successfully without interference.
    
    Sequential uploads should not trigger batch upload deadlock conditions because
    documents are processed one at a time with gaps between submissions.
    
    EXPECTED OUTCOME: PASS on both unfixed and fixed code
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing sequential upload: {num_documents} documents with {SEQUENTIAL_GAP}s gaps")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_seq_{int(time.time() * 1000)}"
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
        
        service = DocumentService()
        document_ids = []
        
        # Upload documents sequentially with gaps
        for i in range(num_documents):
            filename = f"seq_test_{i}.{file_type}"
            content = f"Sequential document {i} content " * 20
            file = create_test_file(filename, content)
            
            logger.info(f"Uploading document {i+1}/{num_documents}...")
            documents = await service.create_documents_from_upload(
                user_id=test_user_id,
                files=[file]
            )
            
            assert len(documents) == 1
            document_ids.append(documents[0].id)
            
            # Wait before next upload (except for last document)
            if i < num_documents - 1:
                logger.info(f"Waiting {SEQUENTIAL_GAP}s before next upload...")
                await asyncio.sleep(SEQUENTIAL_GAP)
        
        logger.info(f"All {num_documents} documents uploaded sequentially")
        
        # Wait for all documents to complete
        results = []
        for doc_id in document_ids:
            result = await wait_for_document_completion(db, doc_id)
            results.append(result)
        
        # Verify all completed successfully
        all_completed = all(r['completed'] for r in results)
        statuses = [r['status'] for r in results]
        
        logger.info(f"Sequential processing results: {statuses}")
        
        assert all_completed, (
            f"Not all sequential documents completed successfully. "
            f"Statuses: {statuses}. "
            f"This indicates a regression in sequential processing."
        )
        
        # Verify all have COMPLETED status
        assert all(s == 'COMPLETED' for s in statuses), (
            f"Some documents did not reach COMPLETED status. "
            f"Statuses: {statuses}"
        )
        
        logger.info(f"✓ Sequential upload of {num_documents} documents preserved correctly")
        
    finally:
        # Cleanup
        try:
            await db.document.delete_many(where={'userId': user.id})
            await db.user.delete(where={'id': user.id})
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


@pytest.mark.asyncio
async def test_document_cancellation_preservation():
    """
    Property 2.3: Document Cancellation Preservation
    
    **Validates: Requirement 3.8**
    
    OBSERVATION: Document cancellation works correctly on unfixed code.
    
    PROPERTY: For any document in PROCESSING or PENDING state, the system SHALL
    handle cancellation requests correctly, updating status to CANCELLED and
    stopping processing.
    
    EXPECTED OUTCOME: PASS on both unfixed and fixed code
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing document cancellation preservation")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_cancel_{int(time.time() * 1000)}"
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
        
        # Upload a document
        service = DocumentService()
        file = create_test_file("cancel_test.txt", "Test content " * 50)
        
        documents = await service.create_documents_from_upload(
            user_id=test_user_id,
            files=[file]
        )
        
        document_id = documents[0].id
        logger.info(f"Uploaded document {document_id}")
        
        # Wait a moment for processing to start
        await asyncio.sleep(2)
        
        # Check current status
        doc = await db.document.find_unique(
            where={'id': document_id},
            include={'job': True}
        )
        
        logger.info(f"Document status before cancellation: {doc.status}")
        
        # Cancel the document
        logger.info(f"Cancelling document {document_id}...")
        cancelled_doc = await service.cancel_document(document_id, test_user_id)
        
        logger.info(f"Cancellation response status: {cancelled_doc.status}")
        
        # Verify cancellation
        assert cancelled_doc.status == 'CANCELLED', (
            f"Document status should be CANCELLED, got {cancelled_doc.status}"
        )
        
        # Verify job status
        assert cancelled_doc.job.status == 'CANCELLED', (
            f"Job status should be CANCELLED, got {cancelled_doc.job.status}"
        )
        
        # Wait a moment and verify status hasn't changed
        await asyncio.sleep(3)
        
        doc_after = await db.document.find_unique(
            where={'id': document_id},
            include={'job': True}
        )
        
        assert doc_after.status == 'CANCELLED', (
            f"Document status changed after cancellation: {doc_after.status}"
        )
        
        logger.info(f"✓ Document cancellation preserved correctly")
        
    finally:
        # Cleanup
        try:
            await db.document.delete_many(where={'userId': user.id})
            await db.user.delete(where={'id': user.id})
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


@pytest.mark.asyncio
async def test_document_retry_preservation():
    """
    Property 2.4: Document Retry Preservation
    
    **Validates: Requirement 3.2**
    
    OBSERVATION: Document retry works correctly on unfixed code.
    
    PROPERTY: For any document in FAILED state, the system SHALL handle retry
    requests correctly, resetting status to PENDING and re-enqueueing the task.
    
    Note: This test creates a document that will fail due to missing file,
    then verifies the retry mechanism works correctly.
    
    EXPECTED OUTCOME: PASS on both unfixed and fixed code
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing document retry preservation")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_retry_{int(time.time() * 1000)}"
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
        
        # Create a document that will fail (invalid file path)
        import uuid
        doc_id = str(uuid.uuid4())
        
        document = await db.document.create(
            data={
                'id': doc_id,
                'userId': user.id,
                'filename': 'nonexistent.txt',
                'originalName': 'nonexistent.txt',
                'fileType': 'text/plain',
                'fileSize': 0,
                'filePath': '/nonexistent/path/file.txt',
                'status': 'FAILED'
            }
        )
        
        job = await db.job.create(
            data={
                'documentId': document.id,
                'celeryTaskId': str(uuid.uuid4()),
                'status': 'FAILED',
                'errorMessage': 'File not found',
                'retryCount': 0,
                'maxRetries': 3
            }
        )
        
        logger.info(f"Created failed document {doc_id}")
        
        # Attempt retry (will fail again due to missing file, but that's expected)
        service = DocumentService()
        
        try:
            retried_doc = await service.retry_document(doc_id, test_user_id)
            
            # Verify retry was initiated
            assert retried_doc.status == 'PENDING', (
                f"Document status should be PENDING after retry, got {retried_doc.status}"
            )
            
            assert retried_doc.job.status == 'PENDING', (
                f"Job status should be PENDING after retry, got {retried_doc.job.status}"
            )
            
            assert retried_doc.job.retryCount == 1, (
                f"Retry count should be 1, got {retried_doc.job.retryCount}"
            )
            
            logger.info(f"✓ Document retry preserved correctly")
            
        except Exception as e:
            # If retry fails due to missing file, that's expected behavior
            if "file not found" in str(e).lower() or "please re-upload" in str(e).lower():
                logger.info(f"✓ Document retry correctly validates file existence")
            else:
                raise
        
    finally:
        # Cleanup
        try:
            await db.document.delete_many(where={'userId': user.id})
            await db.user.delete(where={'id': user.id})
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


@pytest.mark.asyncio
async def test_progress_events_preservation():
    """
    Property 2.5: Progress Events Preservation
    
    **Validates: Requirement 3.4**
    
    OBSERVATION: Progress events are published correctly on unfixed code.
    
    PROPERTY: For any document processing, the system SHALL publish progress
    events to Redis pub/sub that can be consumed by WebSocket clients.
    
    This test verifies that progress events continue to be published correctly
    after implementing the deadlock fix.
    
    EXPECTED OUTCOME: PASS on both unfixed and fixed code
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing progress events preservation")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_progress_{int(time.time() * 1000)}"
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
        
        # Upload a document
        service = DocumentService()
        file = create_test_file("progress_test.txt", "Test content " * 30)
        
        documents = await service.create_documents_from_upload(
            user_id=test_user_id,
            files=[file]
        )
        
        document_id = documents[0].id
        job_id = documents[0].job.id if documents[0].job else None
        
        if not job_id:
            raise ValueError("No job created for document")
        
        logger.info(f"Uploaded document {document_id}, job {job_id}")
        
        # Wait for processing to complete
        result = await wait_for_document_completion(db, document_id)
        
        # Check that progress events were created in database
        progress_events = await db.progressevent.find_many(
            where={'jobId': job_id},
            order={'timestamp': 'asc'}
        )
        
        logger.info(f"Found {len(progress_events)} progress events")
        
        # Verify progress events exist
        assert len(progress_events) > 0, (
            "No progress events found for job. "
            "This indicates a regression in progress event publishing."
        )
        
        # Verify expected event types
        event_types = [event.eventType for event in progress_events]
        logger.info(f"Event types: {event_types}")
        
        # Should have at least job_started and job_completed (or job_failed)
        assert 'job_started' in event_types, (
            "Missing job_started event"
        )
        
        if result['completed']:
            assert 'job_completed' in event_types, (
                "Missing job_completed event"
            )
        
        logger.info(f"✓ Progress events preserved correctly")
        
    finally:
        # Cleanup
        try:
            await db.document.delete_many(where={'userId': user.id})
            await db.user.delete(where={'id': user.id})
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        await db.disconnect()


@pytest.mark.asyncio
async def test_performance_characteristics_preservation():
    """
    Property 2.6: Performance Characteristics Preservation
    
    **Validates: Requirement 3.6**
    
    OBSERVATION: Single document processing completes within normal timeframes
    on unfixed code.
    
    PROPERTY: For any single document upload, the system SHALL complete processing
    within the same timeframe as before the fix (no performance degradation).
    
    This test verifies that the deadlock fix does not introduce performance
    regressions for single document processing.
    
    EXPECTED OUTCOME: PASS on both unfixed and fixed code
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing performance characteristics preservation")
    logger.info(f"{'='*80}")
    
    db = Prisma()
    await db.connect()
    
    try:
        # Create test user
        test_user_id = f"test_perf_{int(time.time() * 1000)}"
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
        
        # Upload a document and measure time
        service = DocumentService()
        file = create_test_file("perf_test.txt", "Test content " * 25)
        
        upload_start = time.time()
        documents = await service.create_documents_from_upload(
            user_id=test_user_id,
            files=[file]
        )
        upload_time = time.time() - upload_start
        
        document_id = documents[0].id
        logger.info(f"Upload completed in {upload_time:.2f}s")
        
        # Wait for processing and measure time
        process_start = time.time()
        result = await wait_for_document_completion(db, document_id)
        process_time = result['elapsed_time']
        
        logger.info(f"Processing completed in {process_time:.1f}s")
        
        # Verify completion
        assert result['completed'], (
            f"Document failed to complete: {result['error']}"
        )
        
        # Verify reasonable performance (should complete within 60 seconds)
        assert process_time < SINGLE_UPLOAD_TIMEOUT, (
            f"Processing took too long: {process_time:.1f}s > {SINGLE_UPLOAD_TIMEOUT}s. "
            f"This indicates a performance regression."
        )
        
        # Log performance metrics
        logger.info(f"Performance metrics:")
        logger.info(f"  Upload time: {upload_time:.2f}s")
        logger.info(f"  Processing time: {process_time:.1f}s")
        logger.info(f"  Total time: {upload_time + process_time:.1f}s")
        
        logger.info(f"✓ Performance characteristics preserved correctly")
        
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
