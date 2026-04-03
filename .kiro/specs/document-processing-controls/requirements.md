# Requirements Document

## Introduction

This feature adds stop/cancel and retry controls to the document processing system. Users need the ability to cancel documents that are currently processing and retry documents that have failed processing. This provides better control over the document processing pipeline and improves the user experience when dealing with processing errors or unwanted operations.

## Glossary

- **Document_Processing_System**: The backend system that processes uploaded documents through Celery tasks
- **Processing_UI**: The frontend interface that displays document processing status
- **Celery_Worker**: The background worker that executes document processing tasks
- **Job**: A database record tracking the processing status of a document
- **Document**: A database record representing an uploaded file
- **Redis_Client**: The Redis client used for pub/sub and cancellation flags
- **API_Endpoint**: A REST API endpoint in the FastAPI backend
- **Stop_Button**: A UI button that allows users to cancel a processing document
- **Retry_Button**: A UI button that allows users to retry a failed document

## Requirements

### Requirement 1: Cancel Processing Document

**User Story:** As a user, I want to stop/cancel a document that is currently processing, so that I can free up resources or stop processing documents I no longer need.

#### Acceptance Criteria

1. WHEN a document has status "PROCESSING" or "QUEUED", THE Processing_UI SHALL display a stop/cancel button
2. WHEN the user clicks the stop button, THE Processing_UI SHALL send a cancellation request to the API_Endpoint
3. WHEN the API_Endpoint receives a cancellation request, THE Document_Processing_System SHALL set a cancellation flag in Redis_Client for the job
4. WHEN the Celery_Worker detects a cancellation flag, THE Celery_Worker SHALL stop processing and update the job status to "CANCELLED"
5. WHEN a job is cancelled, THE Document_Processing_System SHALL update the document status to "CANCELLED"
6. WHEN a job is cancelled, THE Document_Processing_System SHALL publish a cancellation event via Redis_Client pub/sub
7. WHEN the Processing_UI receives a cancellation event, THE Processing_UI SHALL update the document status display to "CANCELLED"

### Requirement 2: Retry Failed Document

**User Story:** As a user, I want to retry processing for documents that failed, so that I can recover from transient errors without re-uploading the file.

#### Acceptance Criteria

1. WHEN a document has status "FAILED", THE Processing_UI SHALL display a retry button
2. WHEN the user clicks the retry button, THE Processing_UI SHALL send a retry request to the API_Endpoint
3. WHEN the API_Endpoint receives a retry request for a failed document, THE Document_Processing_System SHALL validate the document exists and belongs to the user
4. WHEN retrying a document, THE Document_Processing_System SHALL reset the document status to "PENDING"
5. WHEN retrying a document, THE Document_Processing_System SHALL create a new job record or update the existing job status to "PENDING"
6. WHEN retrying a document, THE Document_Processing_System SHALL enqueue a new Celery task for processing
7. WHEN a retry is initiated, THE Document_Processing_System SHALL increment the retry count on the job record
8. IF the retry count exceeds the maximum retries (3), THEN THE Document_Processing_System SHALL reject the retry request with an error message
9. WHEN a retry is successful, THE Processing_UI SHALL update the document status display to "PROCESSING"

### Requirement 3: API Endpoint for Cancellation

**User Story:** As a developer, I want a REST API endpoint to cancel document processing, so that the frontend can trigger cancellations.

#### Acceptance Criteria

1. THE Document_Processing_System SHALL provide a POST endpoint at "/api/v1/documents/{document_id}/cancel"
2. WHEN the cancel endpoint is called, THE API_Endpoint SHALL verify the user owns the document
3. IF the user does not own the document, THEN THE API_Endpoint SHALL return a 403 Forbidden error
4. IF the document does not exist, THEN THE API_Endpoint SHALL return a 404 Not Found error
5. IF the document status is not "PROCESSING" or "QUEUED", THEN THE API_Endpoint SHALL return a 400 Bad Request error with message "Document is not in a cancellable state"
6. WHEN cancellation is successful, THE API_Endpoint SHALL return a 200 OK response with the updated document status
7. WHEN the cancel endpoint is called, THE Document_Processing_System SHALL set a Redis key "job:cancel:{job_id}" with expiration of 1 hour

### Requirement 4: API Endpoint for Retry

**User Story:** As a developer, I want a REST API endpoint to retry failed documents, so that the frontend can trigger retries.

#### Acceptance Criteria

1. THE Document_Processing_System SHALL provide a POST endpoint at "/api/v1/documents/{document_id}/retry"
2. WHEN the retry endpoint is called, THE API_Endpoint SHALL verify the user owns the document
3. IF the user does not own the document, THEN THE API_Endpoint SHALL return a 403 Forbidden error
4. IF the document does not exist, THEN THE API_Endpoint SHALL return a 404 Not Found error
5. IF the document status is not "FAILED", THEN THE API_Endpoint SHALL return a 400 Bad Request error with message "Only failed documents can be retried"
6. IF the retry count exceeds maximum retries, THEN THE API_Endpoint SHALL return a 400 Bad Request error with message "Maximum retry attempts exceeded"
7. WHEN retry is successful, THE API_Endpoint SHALL return a 200 OK response with the updated document status and new job information
8. WHEN the retry endpoint is called, THE Document_Processing_System SHALL clear any previous error messages from the job record

### Requirement 5: UI Controls Display

**User Story:** As a user, I want to see appropriate action buttons based on document status, so that I know what actions are available.

#### Acceptance Criteria

1. WHEN a document has status "PROCESSING" or "QUEUED", THE Processing_UI SHALL display a stop button with a stop icon
2. WHEN a document has status "FAILED", THE Processing_UI SHALL display a retry button with a refresh icon
3. WHEN a document has status "COMPLETED", "CANCELLED", or "PENDING", THE Processing_UI SHALL not display stop or retry buttons
4. WHEN the stop button is clicked, THE Processing_UI SHALL disable the button and show a loading state
5. WHEN the retry button is clicked, THE Processing_UI SHALL disable the button and show a loading state
6. WHEN a cancellation or retry request fails, THE Processing_UI SHALL display an error message to the user
7. WHEN a cancellation or retry request succeeds, THE Processing_UI SHALL show a success notification

### Requirement 6: Graceful Cancellation Handling

**User Story:** As a system administrator, I want document processing to stop gracefully when cancelled, so that no data corruption occurs.

#### Acceptance Criteria

1. WHEN the Celery_Worker checks for cancellation, THE Celery_Worker SHALL check at the start of each major processing stage
2. WHEN a cancellation is detected during parsing, THE Celery_Worker SHALL stop immediately after the current parsing operation completes
3. WHEN a cancellation is detected during extraction, THE Celery_Worker SHALL stop immediately after the current extraction operation completes
4. WHEN processing is cancelled, THE Celery_Worker SHALL clean up any temporary files created during processing
5. WHEN processing is cancelled, THE Celery_Worker SHALL not create or update the ProcessedData record
6. WHEN processing is cancelled, THE Document_Processing_System SHALL publish a progress event with type "job_cancelled"

### Requirement 7: Retry Preserves Original File

**User Story:** As a user, I want retry to use the original uploaded file, so that I don't need to re-upload the document.

#### Acceptance Criteria

1. WHEN retrying a document, THE Document_Processing_System SHALL use the existing filePath from the document record
2. WHEN retrying a document, THE Document_Processing_System SHALL verify the file still exists at the filePath
3. IF the file does not exist at the filePath, THEN THE API_Endpoint SHALL return a 400 Bad Request error with message "Original file not found, please re-upload"
4. WHEN retrying a document, THE Document_Processing_System SHALL delete any existing ProcessedData record for the document
5. WHEN retrying a document, THE Document_Processing_System SHALL clear the errorMessage field on the job record

### Requirement 8: Concurrent Cancellation Safety

**User Story:** As a system administrator, I want cancellation to be safe even if multiple cancel requests are made, so that the system remains stable.

#### Acceptance Criteria

1. WHEN multiple cancel requests are made for the same document, THE Document_Processing_System SHALL handle them idempotently
2. WHEN a cancel request is made for an already cancelled document, THE API_Endpoint SHALL return a 200 OK response with current status
3. WHEN a cancel request is made for a completed document, THE API_Endpoint SHALL return a 400 Bad Request error
4. WHEN the Celery_Worker detects cancellation, THE Celery_Worker SHALL check if the job status is already "CANCELLED" before updating

### Requirement 9: Retry Limit Enforcement

**User Story:** As a system administrator, I want to limit the number of retries, so that failing documents don't consume resources indefinitely.

#### Acceptance Criteria

1. THE Document_Processing_System SHALL enforce a maximum retry limit of 3 attempts per document
2. WHEN a retry is initiated, THE Document_Processing_System SHALL check the current retryCount against maxRetries
3. WHEN the retry limit is reached, THE Processing_UI SHALL display a message "Maximum retry attempts reached" instead of a retry button
4. WHEN the retry limit is reached, THE Processing_UI SHALL suggest the user re-upload the document
5. THE Job record SHALL store both retryCount and maxRetries fields for tracking
