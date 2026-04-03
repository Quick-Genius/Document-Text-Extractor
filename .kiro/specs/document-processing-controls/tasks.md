# Implementation Plan: Document Processing Controls

## Overview

This implementation adds cancel and retry controls to the document processing system. The backend provides REST endpoints for cancellation and retry operations, workers check cancellation flags at strategic points, and the frontend displays appropriate action buttons based on document status. The implementation leverages Redis for cancellation signaling and maintains data consistency through careful state management.

## Tasks

- [ ] 1. Implement backend cancellation endpoint
  - [x] 1.1 Create cancel endpoint in documents.py
    - Add POST route `/api/v1/documents/{document_id}/cancel`
    - Implement ownership verification using `get_current_user_id` dependency
    - Validate document status is PROCESSING or QUEUED
    - Set Redis cancellation flag with 1-hour TTL
    - Update job and document status to CANCELLED
    - Publish cancellation event via Redis pub/sub
    - Return 200 OK response with document status
    - Handle error cases: 403 Forbidden, 404 Not Found, 400 Bad Request
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 1.2 Write property test for cancellation flag creation
    - **Property 4: Cancellation Flag Creation**
    - **Validates: Requirements 1.3, 3.7**
    - Generate random documents with PROCESSING/QUEUED status
    - Call cancel endpoint
    - Verify Redis key `job:cancel:{job_id}` exists with TTL 3600 seconds
    - Tag: `# Feature: document-processing-controls, Property 4`

  - [ ]* 1.3 Write property test for cancellation event publishing
    - **Property 5: Cancellation Event Publishing**
    - **Validates: Requirements 1.6, 6.6**
    - Generate random jobs
    - Cancel them
    - Verify pub/sub event published to channel `progress:{job_id}` with type "job_cancelled"
    - Tag: `# Feature: document-processing-controls, Property 5`

  - [ ]* 1.4 Write property test for cancellation status update
    - **Property 6: Cancellation Status Update**
    - **Validates: Requirements 1.4, 1.5**
    - Generate random jobs with PROCESSING/QUEUED status
    - Cancel them
    - Verify both job status and document status are CANCELLED
    - Tag: `# Feature: document-processing-controls, Property 6`

  - [ ]* 1.5 Write unit tests for cancel endpoint
    - Test successful cancellation
    - Test 404 for non-existent document
    - Test 403 for unauthorized access
    - Test 400 for invalid status (COMPLETED, FAILED, CANCELLED, PENDING)
    - Test Redis flag is set correctly
    - Test pub/sub event published

- [ ] 2. Implement backend retry endpoint
  - [x] 2.1 Create retry endpoint in documents.py
    - Add POST route `/api/v1/documents/{document_id}/retry`
    - Implement ownership verification using `get_current_user_id` dependency
    - Validate document status is FAILED
    - Check retry count against max retries (3)
    - Verify original file exists at filePath
    - Delete existing ProcessedData record if present
    - Reset job status to PENDING, increment retryCount, clear errorMessage
    - Reset document status to PENDING
    - Enqueue new Celery task with original file path
    - Update job with new celeryTaskId
    - Return 200 OK response with document status and job info
    - Handle error cases: 403 Forbidden, 404 Not Found, 400 Bad Request
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 7.1, 7.2, 7.4, 7.5, 9.1, 9.2_

  - [ ]* 2.2 Write property test for retry state management
    - **Property 11-13: Retry Status Reset, Task Enqueue, Count Increment**
    - **Validates: Requirements 2.4, 2.5, 2.6, 2.7, 4.8, 7.1, 7.5**
    - Generate failed documents with various retryCount values (0, 1, 2)
    - Retry them
    - Verify status reset to PENDING, task enqueued, retryCount incremented, errorMessage cleared
    - Tag: `# Feature: document-processing-controls, Property 11-13`

  - [ ]* 2.3 Write property test for retry limit enforcement
    - **Property 14: Retry Limit Enforcement**
    - **Validates: Requirements 2.8, 4.6, 9.1, 9.2**
    - Generate documents with retryCount at various levels (0, 1, 2, 3, 4)
    - Attempt retry
    - Verify rejection with 400 error when retryCount >= 3
    - Tag: `# Feature: document-processing-controls, Property 14`

  - [ ]* 2.4 Write property test for file existence validation
    - **Property 15: File Existence Validation**
    - **Validates: Requirements 7.2**
    - Generate documents with existing and non-existing file paths
    - Attempt retry
    - Verify 400 error when file doesn't exist
    - Tag: `# Feature: document-processing-controls, Property 15`

  - [ ]* 2.5 Write property test for ProcessedData cleanup
    - **Property 16: ProcessedData Cleanup on Retry**
    - **Validates: Requirements 7.4**
    - Generate documents with ProcessedData records
    - Retry them
    - Verify existing ProcessedData deleted before new task enqueued
    - Tag: `# Feature: document-processing-controls, Property 16`

  - [ ]* 2.6 Write unit tests for retry endpoint
    - Test successful retry
    - Test 404 for non-existent document
    - Test 403 for unauthorized access
    - Test 400 for non-failed status
    - Test 400 for exceeded retry limit
    - Test 400 for missing file
    - Test ProcessedData deletion
    - Test task enqueued with correct parameters

- [ ] 3. Checkpoint - Ensure backend endpoints work correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement worker cancellation checks
  - [x] 4.1 Add cancellation check function to tasks.py
    - Create `check_cancellation(job_id: str) -> bool` function
    - Check Redis key `job:cancel:{job_id}` exists
    - Return True if flag exists, False otherwise
    - _Requirements: 1.4, 6.1_

  - [x] 4.2 Add cancellation handler function to tasks.py
    - Create `mark_job_cancelled(db, job_id: str, document_id: str)` function
    - Check if job already cancelled (idempotency)
    - Update job status to CANCELLED
    - Update document status to CANCELLED
    - Publish progress event with type "job_cancelled"
    - _Requirements: 1.4, 1.5, 1.6, 6.6, 8.4_

  - [x] 4.3 Add cancellation checkpoints to process_document_async
    - Add checkpoint before parsing starts
    - Add checkpoint after parsing completes, before extraction
    - Add checkpoint after extraction completes, before storing results
    - At each checkpoint, call `check_cancellation(job_id)`
    - If cancelled, call `mark_job_cancelled` and return early
    - _Requirements: 1.4, 6.1, 6.2, 6.3_

  - [x] 4.4 Ensure temporary file cleanup on cancellation
    - Verify existing `finally` block removes temp files
    - Ensure cleanup happens even when cancelled
    - _Requirements: 6.4_

  - [ ]* 4.5 Write property test for cancellation detection
    - **Property 17: ProcessedData Prevention on Cancellation**
    - **Validates: Requirements 6.5**
    - Generate jobs in various processing stages
    - Set cancellation flag
    - Verify ProcessedData not created when cancelled
    - Tag: `# Feature: document-processing-controls, Property 17`

  - [ ]* 4.6 Write property test for temporary file cleanup
    - **Property 18: Temporary File Cleanup on Cancellation**
    - **Validates: Requirements 6.4**
    - Create temp files during processing
    - Cancel job
    - Verify temp files removed
    - Tag: `# Feature: document-processing-controls, Property 18`

  - [ ]* 4.7 Write unit tests for worker cancellation
    - Test cancellation detected at each checkpoint
    - Test graceful shutdown
    - Test status updates
    - Test temp file cleanup
    - Test no ProcessedData created when cancelled

- [ ] 5. Checkpoint - Ensure worker cancellation works correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement frontend action buttons component
  - [x] 6.1 Create ActionButtons component in frontend
    - Create `ActionButtons.tsx` component
    - Accept props: document, onCancel, onRetry
    - Render stop button for PROCESSING/QUEUED status
    - Render retry button for FAILED status with retryCount < maxRetries
    - Display "Maximum retry attempts reached" message when retryCount >= maxRetries
    - Show loading state during operations
    - Display error messages on failure
    - Use Material Symbols icons: stop_circle, refresh
    - _Requirements: 1.1, 2.1, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 9.3, 9.4_

  - [ ]* 6.2 Write property test for button display logic
    - **Property 1-3: Stop Button Display, Retry Button Display, No Action Buttons**
    - **Validates: Requirements 1.1, 2.1, 5.1, 5.2, 5.3, 9.3**
    - Generate random documents with various statuses and retryCount values
    - Render ActionButtons component
    - Verify correct buttons displayed based on status and retryCount
    - Tag: `# Feature: document-processing-controls, Property 1-3`

  - [ ]* 6.3 Write unit tests for ActionButtons component
    - Test stop button renders for PROCESSING status
    - Test stop button renders for QUEUED status
    - Test retry button renders for FAILED status with retryCount < 3
    - Test max retry message displays when retryCount >= 3
    - Test no buttons for COMPLETED status
    - Test no buttons for CANCELLED status
    - Test no buttons for PENDING status
    - Test loading state during operation
    - Test error display on failure

- [ ] 7. Implement frontend API service functions
  - [x] 7.1 Add cancelDocument function to document service
    - Create `cancelDocument(api: AxiosInstance, documentId: string)` function
    - Make POST request to `/api/v1/documents/${documentId}/cancel`
    - Return response data
    - Handle errors appropriately
    - _Requirements: 1.2, 3.1_

  - [x] 7.2 Add retryDocument function to document service
    - Create `retryDocument(api: AxiosInstance, documentId: string)` function
    - Make POST request to `/api/v1/documents/${documentId}/retry`
    - Return response data
    - Handle errors appropriately
    - _Requirements: 2.2, 4.1_

  - [ ]* 7.3 Write unit tests for service functions
    - Test cancelDocument makes correct API call
    - Test retryDocument makes correct API call
    - Test error handling for both functions

- [ ] 8. Integrate action buttons into document list UI
  - [x] 8.1 Import and use ActionButtons component in document list
    - Import ActionButtons component
    - Pass document, onCancel, onRetry props
    - Implement onCancel handler to call cancelDocument API
    - Implement onRetry handler to call retryDocument API
    - Show success notification on successful operation
    - Show error notification on failed operation
    - Update document list after operation completes
    - _Requirements: 1.2, 2.2, 5.6, 5.7_

  - [ ]* 8.2 Write integration tests for cancel flow
    - Mock API responses
    - Trigger cancel button click
    - Verify API called correctly
    - Verify UI updates correctly
    - Verify success notification shown

  - [ ]* 8.3 Write integration tests for retry flow
    - Mock API responses
    - Trigger retry button click
    - Verify API called correctly
    - Verify UI updates correctly
    - Verify success notification shown

- [ ] 9. Implement property tests for ownership and authorization
  - [ ]* 9.1 Write property test for ownership verification
    - **Property 7-8: Ownership Verification and Unauthorized Access Error**
    - **Validates: Requirements 3.2, 3.3, 4.2, 4.3**
    - Generate random documents owned by different users
    - Attempt cancel/retry with wrong user
    - Verify 403 error returned
    - Tag: `# Feature: document-processing-controls, Property 7-8`

  - [ ]* 9.2 Write property test for invalid status errors
    - **Property 9-10: Invalid Status Cancellation/Retry Error**
    - **Validates: Requirements 3.5, 4.5**
    - Generate documents with various statuses
    - Attempt cancel on non-cancellable statuses
    - Attempt retry on non-failed statuses
    - Verify 400 errors with correct messages
    - Tag: `# Feature: document-processing-controls, Property 9-10`

  - [ ]* 9.3 Write property test for cancellation idempotency
    - **Property 19: Cancellation Idempotency**
    - **Validates: Requirements 8.1, 8.2**
    - Generate random documents
    - Send multiple cancel requests
    - Verify consistent final state (CANCELLED status, flag set)
    - Verify subsequent requests return 200 OK
    - Tag: `# Feature: document-processing-controls, Property 19`

  - [ ]* 9.4 Write property test for response format
    - **Property 20-21: Successful Cancellation/Retry Response**
    - **Validates: Requirements 3.6, 4.7**
    - Generate random successful operations
    - Verify response contains required fields (id, status, message, job info)
    - Tag: `# Feature: document-processing-controls, Property 20-21`

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties with minimum 100 iterations
- Unit tests validate specific examples and edge cases
- The implementation uses Python (FastAPI) for backend and TypeScript (React) for frontend
- Redis is used for cancellation flags and pub/sub events
- PostgreSQL maintains authoritative state for documents and jobs
