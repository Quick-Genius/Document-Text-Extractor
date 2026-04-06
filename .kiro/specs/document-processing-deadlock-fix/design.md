# Document Processing Deadlock Fix Design

## Overview

This bugfix addresses critical concurrency and deadlock issues in the document processing pipeline that cause batch uploads to hang indefinitely. The system currently suffers from eight distinct but interrelated problems: lack of transaction isolation, missing connection pooling, absence of database locking, Redis singleton deadlocks in async contexts, uncoordinated Celery task execution, missing checkpoint validation, no operation timeouts, and inadequate rate limiting.

The fix implements a comprehensive solution that maintains backward compatibility while adding robust concurrency controls. The approach focuses on minimal invasive changes to existing code paths while introducing new infrastructure for transaction management, connection pooling, distributed locking, and timeout handling.

## Glossary

- **Bug_Condition (C)**: The condition that triggers deadlocks - when multiple documents are uploaded in a batch causing concurrent database operations, connection pool exhaustion, and Redis singleton conflicts
- **Property (P)**: The desired behavior - batch uploads complete successfully with proper transaction isolation, connection pooling, locking, task coordination, and timeout handling
- **Preservation**: Single document uploads and sequential processing that must continue working exactly as before
- **Transaction Isolation**: Database transactions with appropriate isolation levels to prevent race conditions during concurrent operations
- **Connection Pooling**: Reusing database connections across operations to prevent connection exhaustion
- **Row-Level Locking**: PostgreSQL SELECT FOR UPDATE to ensure atomic read-modify-write operations
- **Task-Scoped Redis**: Creating separate Redis client instances per Celery task to avoid singleton deadlocks
- **Distributed Lock**: Redis-based coordination mechanism to serialize critical sections across Celery workers
- **Checkpoint Validation**: Periodic checks during long-running operations to detect and recover from hung tasks
- **Operation Timeout**: Maximum time limit for database operations to prevent indefinite blocking
- **Rate Limiting**: Controlling the number of concurrent tasks to prevent system overload

## Bug Details

### Bug Condition

The bug manifests when multiple documents are uploaded simultaneously in a batch. The system creates concurrent Celery tasks that perform database operations without proper isolation, exhaust the connection pool, compete for job status updates without locking, share a singleton Redis connection across async contexts causing deadlocks, execute without coordination leading to resource contention, lack checkpoint validation causing indefinite hangs, have no timeout protection causing worker thread blocking, and overwhelm the system without rate limiting.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type BatchUploadRequest
  OUTPUT: boolean
  
  RETURN input.documentCount >= 2
         AND concurrentCeleryTasksCreated(input.documentCount)
         AND (
           noTransactionIsolation() OR
           noConnectionPooling() OR
           noDatabaseLocking() OR
           redisSingletonUsed() OR
           noTaskCoordination() OR
           noCheckpointValidation() OR
           noOperationTimeouts() OR
           noRateLimiting()
         )
END FUNCTION
```

### Examples

- **Batch Upload of 5 Documents**: User uploads 5 PDFs simultaneously. System creates 5 Celery tasks that execute concurrently. Tasks compete for database connections causing pool exhaustion. Multiple tasks attempt to update job status simultaneously causing lost updates. Tasks share Redis singleton causing deadlock in finally blocks. All 5 documents remain in PENDING status indefinitely.

- **Batch Upload of 10 Documents**: User uploads 10 documents. System creates 10 concurrent tasks overwhelming the worker pool. Database operations execute without transactions causing race conditions. No rate limiting allows all 10 tasks to start simultaneously. Connection pool (default 10 connections) is exhausted. Tasks hang waiting for connections that never become available.

- **Concurrent Batch Uploads**: Two users upload batches of 3 documents each simultaneously. Total of 6 concurrent tasks execute. Tasks attempt to update job status without row-level locking causing lost updates. Redis singleton is accessed from multiple async contexts causing deadlock. Some tasks complete while others hang indefinitely.

- **Edge Case - Single Document Upload**: User uploads 1 document. System creates 1 Celery task. No concurrency issues occur. Document processes successfully. This behavior must be preserved.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Single document uploads must continue to process successfully without any performance degradation
- Sequential document processing by a single worker must continue to work exactly as before
- Successful task completion must continue to update document and job status correctly
- Redis pub/sub events for progress updates must continue to be delivered to WebSocket clients
- Database operations that complete within normal timeframes must not trigger timeout mechanisms
- System operation under normal load conditions must maintain existing performance characteristics
- Document processing failures due to legitimate errors (invalid file, extraction failure) must continue to mark jobs as FAILED with appropriate error messages
- User-initiated cancellation requests must continue to be handled correctly

**Scope:**
All inputs that do NOT involve batch uploads (2+ documents uploaded simultaneously) should be completely unaffected by this fix. This includes:
- Single document uploads via API
- Sequential document uploads with time gaps between uploads
- Document retry operations
- Document cancellation operations
- Progress event publishing
- WebSocket notifications

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Missing Transaction Isolation**: The `create_documents_from_upload` function in `document_service.py` creates multiple document and job records in a loop without wrapping operations in a transaction. This causes race conditions when multiple batch uploads occur simultaneously, leading to lost updates and inconsistent state.

2. **No Connection Pooling**: Each Prisma operation creates a new database connection via `get_prisma()` and `await db.connect()`. With default PostgreSQL connection limits (typically 100), batch uploads quickly exhaust the pool. The code has no connection pooling configuration or connection reuse strategy.

3. **Lack of Database Locking**: The `update_job_status` function in `tasks.py` performs read-modify-write operations without row-level locking. When multiple workers update the same job concurrently, the last write wins, causing lost updates and inconsistent job state.

4. **Redis Singleton Deadlock**: The `redis_client` singleton in `redis_client.py` is shared across multiple Celery tasks. Each task runs in a separate `asyncio.run()` call. When tasks attempt to close the shared connection in finally blocks, they deadlock waiting for each other, causing tasks to hang indefinitely.

5. **No Task Coordination**: Celery tasks execute concurrently without any coordination mechanism. The `celery_app.py` configuration has `worker_concurrency=1` but this only limits concurrency per worker process. Multiple worker processes or multiple batch uploads still cause uncontrolled concurrent execution.

6. **Missing Checkpoint Validation**: The `process_document_async` function has stage timeouts for parsing, extraction, and storing, but no checkpoint validation between stages. If a task hangs between stages (e.g., during database operations), it remains hung indefinitely without recovery.

7. **No Operation Timeouts**: Prisma database operations have no timeout configuration. The `await db.document.create()` and `await db.job.update()` calls can block indefinitely if the database is slow or deadlocked, causing the entire worker thread to hang.

8. **Inadequate Rate Limiting**: The system has no rate limiting or queue depth checking. When a user uploads 50 documents, the system creates 50 concurrent Celery tasks immediately, overwhelming the worker pool, exhausting database connections, and causing system-wide resource exhaustion.

## Correctness Properties

Property 1: Bug Condition - Batch Upload Processing

_For any_ batch upload where 2 or more documents are uploaded simultaneously, the fixed system SHALL process all documents successfully by implementing transaction isolation for database operations, connection pooling for Prisma clients, row-level locking for job status updates, task-scoped Redis clients to avoid singleton deadlocks, distributed locking for task coordination, checkpoint validation to detect hung tasks, operation timeouts to prevent indefinite blocking, and rate limiting to prevent system overload.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**

Property 2: Preservation - Single Document and Sequential Processing

_For any_ upload that is NOT a batch upload (single document or sequential uploads with time gaps), the fixed system SHALL produce exactly the same behavior as the original system, preserving all existing functionality for single document uploads, sequential processing, task completion, progress events, cancellation handling, and error handling.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `backend/app/services/document_service.py`

**Function**: `create_documents_from_upload`

**Specific Changes**:
1. **Add Transaction Isolation**: Wrap the document creation loop in a Prisma transaction with READ COMMITTED isolation level
   - Use `async with db.tx()` context manager to ensure atomic batch creation
   - Rollback entire batch if any document creation fails
   - Prevents race conditions when multiple batch uploads occur simultaneously

2. **Implement Rate Limiting**: Add queue depth validation before creating tasks
   - Query count of PENDING + PROCESSING documents before batch upload
   - Reject batch if queue depth exceeds configurable threshold (e.g., 50 documents)
   - Return 429 Too Many Requests with retry-after header

**File**: `backend/app/workers/tasks.py`

**Function**: `process_document_async`

**Specific Changes**:
3. **Add Connection Pooling**: Configure Prisma connection pool in `get_prisma()`
   - Add connection pool configuration to Prisma client initialization
   - Set pool_size to 20 connections (configurable via environment variable)
   - Set pool_timeout to 30 seconds to prevent indefinite waiting
   - Reuse connections across operations within the same task

4. **Implement Database Locking**: Add row-level locking to `update_job_status`
   - Use `db.job.find_unique(where={"id": job_id}, include={"_count": {"select": {"id": True}}})` with raw SQL `FOR UPDATE` clause
   - Wrap update in transaction to ensure atomic read-modify-write
   - Prevents lost updates when multiple workers update the same job

5. **Replace Redis Singleton**: Use `create_task_redis()` instead of `redis_client`
   - Already implemented in current code - verify all call sites use task-scoped client
   - Ensure `task_redis.close()` is called in finally block with timeout
   - Prevents singleton deadlock across multiple async contexts

6. **Add Checkpoint Validation**: Implement checkpoint checks between processing stages
   - After parsing stage: check if task has exceeded total timeout (15 minutes)
   - After extraction stage: check if task has exceeded total timeout
   - Before storing stage: check if task has exceeded total timeout
   - If timeout exceeded, raise exception to fail task gracefully

7. **Implement Operation Timeouts**: Add timeouts to all Prisma operations
   - Wrap `db.document.create()` in `asyncio.wait_for()` with 10 second timeout
   - Wrap `db.job.update()` in `asyncio.wait_for()` with 10 second timeout
   - Wrap `db.processeddata.create()` in `asyncio.wait_for()` with 30 second timeout
   - On timeout, log error and raise exception to fail task gracefully

**File**: `backend/app/workers/celery_app.py`

**Function**: Celery configuration

**Specific Changes**:
8. **Add Task Serialization**: Implement distributed locking for batch upload coordination
   - Add Redis-based distributed lock using `redis.lock()` with timeout
   - Acquire lock before starting document processing
   - Release lock in finally block after processing completes
   - Limits concurrent task execution to prevent resource exhaustion

9. **Configure Task Routing**: Add task routing to separate queues for batch vs single uploads
   - Create "batch" queue for batch upload tasks with lower concurrency
   - Create "single" queue for single upload tasks with higher concurrency
   - Route tasks based on batch size to prevent batch uploads from blocking single uploads

**File**: `backend/app/core/config.py`

**Function**: Settings class

**Specific Changes**:
10. **Add Configuration Parameters**: Add new environment variables for concurrency controls
    - `PRISMA_POOL_SIZE`: Connection pool size (default 20)
    - `PRISMA_POOL_TIMEOUT`: Connection pool timeout in seconds (default 30)
    - `PRISMA_OPERATION_TIMEOUT`: Individual operation timeout in seconds (default 10)
    - `TASK_TOTAL_TIMEOUT`: Total task timeout in seconds (default 900 = 15 minutes)
    - `BATCH_UPLOAD_MAX_QUEUE_DEPTH`: Maximum pending documents before rejecting batch (default 50)
    - `BATCH_UPLOAD_MAX_CONCURRENT_TASKS`: Maximum concurrent batch tasks (default 5)

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the deadlock bugs on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the deadlock bugs BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate batch uploads with concurrent Celery task execution. Run these tests on the UNFIXED code to observe deadlocks, connection pool exhaustion, and Redis singleton conflicts. Monitor system behavior to understand the root causes.

**Test Cases**:
1. **Batch Upload Deadlock Test**: Upload 5 documents simultaneously and observe that documents remain in PENDING status indefinitely (will fail on unfixed code)
2. **Connection Pool Exhaustion Test**: Upload 15 documents simultaneously and observe connection pool exhaustion errors in logs (will fail on unfixed code)
3. **Redis Singleton Deadlock Test**: Upload 3 documents simultaneously and observe tasks hanging in finally blocks when closing Redis connections (will fail on unfixed code)
4. **Lost Update Test**: Upload 2 documents simultaneously and observe job status updates being lost due to concurrent writes without locking (will fail on unfixed code)
5. **Rate Limiting Test**: Upload 100 documents simultaneously and observe system overload with worker threads exhausted (will fail on unfixed code)

**Expected Counterexamples**:
- Documents remain in PENDING status after 5 minutes
- Database connection pool exhaustion errors in logs: "connection pool timeout"
- Redis connection errors in logs: "connection already closed" or "deadlock detected"
- Job status inconsistencies: status shows PROCESSING but document shows PENDING
- Worker threads blocked indefinitely with no progress events published

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (batch uploads), the fixed system produces the expected behavior (successful processing with proper concurrency controls).

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := process_batch_upload_fixed(input)
  ASSERT result.all_documents_completed = true
  ASSERT result.no_deadlocks = true
  ASSERT result.no_connection_exhaustion = true
  ASSERT result.no_redis_conflicts = true
  ASSERT result.proper_transaction_isolation = true
  ASSERT result.proper_locking = true
  ASSERT result.proper_timeouts = true
  ASSERT result.proper_rate_limiting = true
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (single document uploads, sequential uploads), the fixed system produces the same result as the original system.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT process_upload_original(input) = process_upload_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-batch inputs

**Test Plan**: Observe behavior on UNFIXED code first for single document uploads and sequential uploads, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Single Document Upload Preservation**: Observe that single document uploads complete successfully on unfixed code, then write test to verify this continues after fix
2. **Sequential Upload Preservation**: Observe that sequential uploads (with 5 second gaps) complete successfully on unfixed code, then write test to verify this continues after fix
3. **Cancellation Preservation**: Observe that document cancellation works correctly on unfixed code, then write test to verify this continues after fix
4. **Retry Preservation**: Observe that document retry works correctly on unfixed code, then write test to verify this continues after fix
5. **Progress Event Preservation**: Observe that progress events are published correctly on unfixed code, then write test to verify this continues after fix

### Unit Tests

- Test transaction isolation by simulating concurrent batch uploads and verifying no race conditions
- Test connection pooling by monitoring connection count during batch uploads
- Test database locking by simulating concurrent job status updates and verifying no lost updates
- Test task-scoped Redis by verifying each task creates and closes its own connection
- Test checkpoint validation by simulating long-running tasks and verifying timeout detection
- Test operation timeouts by mocking slow database operations and verifying timeout exceptions
- Test rate limiting by uploading batches that exceed queue depth and verifying rejection

### Property-Based Tests

- Generate random batch sizes (2-20 documents) and verify all documents complete successfully
- Generate random document types (PDF, DOCX, images, text) and verify processing works for all types
- Generate random timing patterns (simultaneous vs staggered uploads) and verify no deadlocks
- Generate random failure scenarios (database slow, Redis unavailable) and verify graceful degradation
- Test that all single document uploads continue to work across many scenarios

### Integration Tests

- Test full batch upload flow with 10 documents and verify all complete successfully
- Test concurrent batch uploads from multiple users and verify no interference
- Test batch upload with rate limiting triggered and verify proper 429 response
- Test batch upload with connection pool exhaustion and verify graceful recovery
- Test batch upload with Redis unavailable and verify fallback behavior
- Test that WebSocket clients receive progress events for all documents in batch
- Test that database state is consistent after batch upload completes
