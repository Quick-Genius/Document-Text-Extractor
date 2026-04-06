# Bugfix Requirements Document

## Introduction

This document specifies the requirements for fixing a critical bug where documents get stuck at PENDING status during batch uploads (2+ files). The root cause is that Celery task enqueuing happens after the database transaction commits, without proper error handling. If task enqueuing fails (e.g., Redis connection issues, Celery broker problems), documents remain PENDING forever with no fallback mechanism to mark them as FAILED or retry the enqueuing.

The fix ensures reliable task enqueuing with proper error handling, logging, and fallback mechanisms to prevent documents from being stuck in PENDING status indefinitely.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN batch upload transaction commits successfully AND Celery task enqueuing fails for any document THEN the system leaves that document at PENDING status with no error indication

1.2 WHEN batch upload transaction commits successfully AND Redis/Celery broker is unavailable THEN the system does not log the task enqueuing failure and documents remain PENDING

1.3 WHEN batch upload transaction commits successfully AND task enqueuing fails for one document in a batch THEN the system continues processing other documents without marking the failed document as FAILED

1.4 WHEN batch upload transaction commits successfully AND the job update with Celery task ID fails THEN the system does not handle the error and the job retains the temporary UUID

### Expected Behavior (Correct)

2.1 WHEN batch upload transaction commits successfully AND Celery task enqueuing fails for any document THEN the system SHALL mark that document as FAILED with an appropriate error message

2.2 WHEN batch upload transaction commits successfully AND Redis/Celery broker is unavailable THEN the system SHALL log the task enqueuing failure with detailed error information

2.3 WHEN batch upload transaction commits successfully AND task enqueuing fails for one document in a batch THEN the system SHALL mark that specific document as FAILED while continuing to process other documents successfully

2.4 WHEN batch upload transaction commits successfully AND the job update with Celery task ID fails THEN the system SHALL handle the error gracefully and mark the document as FAILED

2.5 WHEN batch upload transaction commits successfully AND all tasks are enqueued successfully THEN the system SHALL update all job records with actual Celery task IDs

### Unchanged Behavior (Regression Prevention)

3.1 WHEN single document upload (1 file) is processed THEN the system SHALL CONTINUE TO use the existing non-transactional flow

3.2 WHEN batch upload transaction commits successfully AND all tasks enqueue successfully THEN the system SHALL CONTINUE TO return all documents with PENDING status and valid job information

3.3 WHEN batch upload is rejected due to queue depth limits THEN the system SHALL CONTINUE TO raise ValidationError before any database operations

3.4 WHEN documents are successfully enqueued THEN the system SHALL CONTINUE TO log the task ID and document ID for tracking

3.5 WHEN storage service fails to save a file THEN the system SHALL CONTINUE TO raise an exception and roll back the transaction (for batch uploads)
