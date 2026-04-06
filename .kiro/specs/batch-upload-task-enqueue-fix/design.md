# Batch Upload Task Enqueuing Bugfix Design

## Overview

This design addresses a critical bug where documents get stuck at PENDING status during batch uploads when Celery task enqueuing fails after the database transaction commits. The current implementation enqueues tasks outside the transaction without proper error handling, leaving documents in PENDING status indefinitely if Redis/Celery broker issues occur.

The fix implements comprehensive error handling with:
- Try-catch blocks around task enqueuing operations
- Automatic document/job status updates to FAILED on enqueue errors
- Detailed error logging for debugging
- Graceful degradation that marks failed documents while continuing with successful ones
- Preservation of single-file upload behavior

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when task enqueuing fails after transaction commit
- **Property (P)**: The desired behavior when enqueuing fails - documents should be marked FAILED with error details
- **Preservation**: Single-file upload behavior and successful batch upload flows that must remain unchanged
- **create_documents_from_upload**: The function in `backend/app/services/document_service.py` that handles file uploads and creates database records
- **process_document_task.delay()**: The Celery method that enqueues asynchronous document processing tasks
- **created_docs**: The list of document/job records created within the transaction, used for post-commit task enqueuing

## Bug Details

### Bug Condition

The bug manifests when the database transaction commits successfully but Celery task enqueuing fails for one or more documents in a batch upload. The `create_documents_from_upload` function enqueues tasks after transaction commit without error handling, leaving documents at PENDING status with no mechanism to detect or recover from enqueue failures.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type BatchUploadContext
  OUTPUT: boolean
  
  RETURN input.filesCount >= 2
         AND input.transactionCommitted == true
         AND (input.celeryBrokerAvailable == false 
              OR input.taskEnqueueFailed == true
              OR input.jobUpdateFailed == true)
         AND input.documentStatus == "PENDING"
END FUNCTION
```

### Examples

- **Redis Connection Failure**: User uploads 5 files, transaction commits successfully creating 5 PENDING documents, Redis connection fails during task enqueuing, all 5 documents remain PENDING forever with no error indication
- **Celery Broker Unavailable**: User uploads 3 files, transaction commits, Celery broker is down, `process_document_task.delay()` raises exception, documents stay PENDING with no logging
- **Partial Enqueue Failure**: User uploads 10 files, transaction commits, first 7 tasks enqueue successfully, 8th task fails due to broker issue, documents 8-10 remain PENDING while 1-7 process normally
- **Job Update Failure**: User uploads 2 files, transaction commits, tasks enqueue successfully, but job update with Celery task ID fails due to database timeout, jobs retain temporary UUID and documents stay PENDING

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Single-file uploads (1 file) must continue to use the existing non-transactional flow
- Successful batch uploads where all tasks enqueue must continue to return PENDING documents with valid job information
- Queue depth validation must continue to reject uploads before any database operations
- Storage service failures must continue to raise exceptions and roll back transactions
- Successfully enqueued tasks must continue to log task ID and document ID for tracking

**Scope:**
All inputs that do NOT involve task enqueuing failures should be completely unaffected by this fix. This includes:
- Single-file uploads
- Successful batch uploads with no enqueue errors
- Upload rejections due to queue depth limits
- Transaction rollbacks due to storage failures

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Missing Error Handling**: The task enqueuing loop has no try-catch blocks to handle exceptions from `process_document_task.delay()` or `db.job.update()`
   - Lines 127-140 in `document_service.py` perform enqueuing without exception handling
   - If `task_result = process_document_task.delay()` raises an exception, the entire function fails
   - If `db.job.update()` times out or fails, the job retains the temporary UUID

2. **Post-Transaction Enqueuing**: Tasks are enqueued after the transaction commits, creating a window where documents exist in PENDING state but tasks haven't been enqueued yet
   - Transaction commits at line 125
   - Task enqueuing happens at lines 127-140
   - If enqueuing fails, there's no mechanism to update the already-committed documents

3. **No Fallback Mechanism**: When enqueuing fails, there's no code to mark documents as FAILED or log the error
   - No status update to FAILED when enqueuing fails
   - No error message stored in job record
   - No logging of enqueue failures for debugging

4. **All-or-Nothing Failure**: A single enqueue failure causes the entire batch to fail, even though other documents could be processed successfully
   - The loop doesn't continue after an enqueue failure
   - Partial success is not handled

## Correctness Properties

Property 1: Bug Condition - Task Enqueue Failure Handling

_For any_ batch upload where the transaction commits successfully and task enqueuing fails for one or more documents, the fixed function SHALL mark those specific documents as FAILED with detailed error messages, update their job records with error information, and log the failures for debugging.

**Validates: Requirements 2.1, 2.2, 2.4**

Property 2: Bug Condition - Partial Batch Success

_For any_ batch upload where the transaction commits successfully and task enqueuing fails for some documents but succeeds for others, the fixed function SHALL mark failed documents as FAILED while allowing successful documents to proceed with PENDING status and valid Celery task IDs.

**Validates: Requirements 2.3, 2.5**

Property 3: Preservation - Single File Upload Behavior

_For any_ single-file upload (1 file), the fixed function SHALL produce exactly the same behavior as the original function, preserving the non-transactional flow and error handling.

**Validates: Requirements 3.1**

Property 4: Preservation - Successful Batch Upload Behavior

_For any_ batch upload where all tasks enqueue successfully, the fixed function SHALL produce exactly the same result as the original function, returning all documents with PENDING status and valid job information.

**Validates: Requirements 3.2, 3.4**

Property 5: Preservation - Pre-Transaction Validation

_For any_ upload that fails pre-transaction validation (queue depth limits, storage failures), the fixed function SHALL produce exactly the same behavior as the original function, raising appropriate exceptions before any database operations.

**Validates: Requirements 3.3, 3.5**

## Fix Implementation

### Changes Required

**File**: `backend/app/services/document_service.py`

**Function**: `create_documents_from_upload`

**Specific Changes**:

1. **Wrap Task Enqueuing in Try-Catch**: Add exception handling around the task enqueuing loop (lines 127-140)
   - Catch exceptions from `process_document_task.delay()`
   - Catch exceptions from `db.job.update()`
   - Log detailed error information including document ID, job ID, and exception details
   - Continue processing other documents in the batch after a failure

2. **Mark Failed Documents**: When enqueuing fails, update document and job status to FAILED
   - Update document status to "FAILED" using `db.document.update()`
   - Update job status to "FAILED" using `db.job.update()`
   - Store error message in job's `errorMessage` field
   - Set job's `failedAt` timestamp

3. **Implement Partial Success Handling**: Track successful and failed enqueues separately
   - Maintain a list of successfully enqueued documents
   - Maintain a list of failed documents with error details
   - Return all documents (both successful and failed) in the response
   - Log summary of batch results (e.g., "5/10 documents enqueued successfully, 5 failed")

4. **Add Configuration for Retry Behavior**: Add settings for enqueue retry logic
   - `TASK_ENQUEUE_MAX_RETRIES`: Number of retry attempts for task enqueuing (default: 3)
   - `TASK_ENQUEUE_RETRY_DELAY`: Delay between retry attempts in seconds (default: 1)
   - Implement exponential backoff for retries

5. **Enhance Error Logging**: Add structured logging for debugging
   - Log each enqueue attempt with document ID and attempt number
   - Log enqueue failures with full exception details and stack trace
   - Log final batch summary with success/failure counts
   - Include Redis/Celery broker connection status in error logs

### Implementation Pseudocode

```python
# After transaction commits (line 125)
successful_docs = []
failed_docs = []

for doc_info in created_docs:
    enqueue_success = False
    last_error = None
    
    # Retry logic for task enqueuing
    for attempt in range(1, settings.TASK_ENQUEUE_MAX_RETRIES + 1):
        try:
            # Attempt to enqueue task
            task_result = process_document_task.delay(
                document_id=doc_info["document_id"],
                file_path=doc_info["file_path"]
            )
            
            # Attempt to update job with Celery task ID
            await db.job.update(
                where={"id": doc_info["job_id"]},
                data={"celeryTaskId": task_result.id}
            )
            
            logger.info(f"Enqueued task for document {doc_info['document_id']}, task_id: {task_result.id}")
            successful_docs.append(doc_info)
            enqueue_success = True
            break
            
        except Exception as e:
            last_error = e
            logger.warning(f"Enqueue attempt {attempt}/{settings.TASK_ENQUEUE_MAX_RETRIES} failed for document {doc_info['document_id']}: {e}")
            
            if attempt < settings.TASK_ENQUEUE_MAX_RETRIES:
                await asyncio.sleep(settings.TASK_ENQUEUE_RETRY_DELAY * attempt)  # Exponential backoff
    
    # If all retries failed, mark document as FAILED
    if not enqueue_success:
        try:
            error_msg = f"Failed to enqueue processing task after {settings.TASK_ENQUEUE_MAX_RETRIES} attempts: {last_error}"
            
            # Update document status to FAILED
            await db.document.update(
                where={"id": doc_info["document_id"]},
                data={"status": "FAILED"}
            )
            
            # Update job status to FAILED with error details
            await db.job.update(
                where={"id": doc_info["job_id"]},
                data={
                    "status": "FAILED",
                    "failedAt": datetime.now(),
                    "errorMessage": error_msg
                }
            )
            
            logger.error(f"Marked document {doc_info['document_id']} as FAILED: {error_msg}")
            failed_docs.append({"doc_info": doc_info, "error": error_msg})
            
        except Exception as update_error:
            logger.error(f"Failed to update document/job status to FAILED: {update_error}", exc_info=True)

# Log batch summary
logger.info(f"Batch upload complete: {len(successful_docs)}/{len(created_docs)} documents enqueued successfully, {len(failed_docs)} failed")

# Fetch all documents (successful and failed) for response
# ... existing code to build DocumentResponse list ...
```

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code by simulating enqueue failures, then verify the fix correctly handles failures and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm that enqueue failures leave documents in PENDING status.

**Test Plan**: Write tests that mock Celery task enqueuing to raise exceptions, then verify documents remain PENDING on unfixed code. Run these tests to observe the bug and validate our root cause analysis.

**Test Cases**:
1. **Redis Connection Failure Test**: Mock `process_document_task.delay()` to raise `redis.ConnectionError`, upload 3 files, verify all documents remain PENDING (will fail on unfixed code)
2. **Celery Broker Unavailable Test**: Mock Celery broker to be unavailable, upload 5 files, verify documents remain PENDING and no error is logged (will fail on unfixed code)
3. **Partial Enqueue Failure Test**: Mock enqueuing to succeed for first 2 documents and fail for 3rd, verify document 3 remains PENDING while 1-2 process (will fail on unfixed code)
4. **Job Update Failure Test**: Mock `db.job.update()` to raise timeout exception, verify job retains temporary UUID and document stays PENDING (will fail on unfixed code)

**Expected Counterexamples**:
- Documents remain at PENDING status when enqueuing fails
- No error messages are stored in job records
- No logging of enqueue failures
- Entire batch fails when one document's enqueue fails

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (enqueue failures), the fixed function marks documents as FAILED with error details.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := create_documents_from_upload_fixed(input)
  ASSERT result.failedDocuments[i].status == "FAILED"
  ASSERT result.failedDocuments[i].job.errorMessage != null
  ASSERT result.failedDocuments[i].job.failedAt != null
  ASSERT logContains(f"Marked document {doc_id} as FAILED")
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (successful enqueues, single-file uploads), the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT create_documents_from_upload_original(input) = create_documents_from_upload_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (different file counts, types, sizes)
- It catches edge cases that manual unit tests might miss (e.g., exactly 2 files, 10 files, mixed file types)
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for successful uploads, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Single File Upload Preservation**: Verify single-file uploads continue to work exactly as before (non-transactional flow)
2. **Successful Batch Upload Preservation**: Verify successful batch uploads return all documents with PENDING status and valid job IDs
3. **Queue Depth Rejection Preservation**: Verify queue depth validation continues to reject uploads before database operations
4. **Storage Failure Preservation**: Verify storage failures continue to roll back transactions

### Unit Tests

- Test task enqueuing with mocked Redis connection failures
- Test task enqueuing with mocked Celery broker unavailability
- Test partial batch success (some enqueues succeed, some fail)
- Test job update failures after successful task enqueuing
- Test retry logic with exponential backoff
- Test error logging for enqueue failures
- Test document/job status updates to FAILED
- Test single-file upload preservation
- Test successful batch upload preservation

### Property-Based Tests

- Generate random batch sizes (2-10 files) and verify correct handling of enqueue failures
- Generate random failure patterns (fail at different positions in batch) and verify partial success handling
- Generate random file types and sizes and verify preservation of successful upload behavior
- Test that all non-enqueue-failure scenarios produce identical results to original code

### Integration Tests

- Test full batch upload flow with real Redis/Celery (if available in test environment)
- Test batch upload with Redis temporarily unavailable (using Docker container stop/start)
- Test batch upload with mixed success/failure and verify frontend receives correct status updates
- Test that failed documents can be re-uploaded successfully
- Test that successful documents in a partially-failed batch process normally

