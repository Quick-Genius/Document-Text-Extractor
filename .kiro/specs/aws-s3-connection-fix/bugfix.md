# Bugfix Requirements Document

## Introduction

The AWS S3 connection health check returns `s3_connected: false` even when `STORAGE_TYPE=s3` is configured with valid AWS credentials in `backend/.env`. The root cause is that `app/core/config.py` loads environment variables from the wrong `.env` file path - it loads from the project root `.env` instead of `backend/.env` where the AWS credentials are defined.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN config.py loads .env from project root (./.env) THEN the AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET, STORAGE_TYPE) are NOT loaded because they only exist in backend/.env
1.2 WHEN check_aws_s3() runs THEN it sees STORAGE_TYPE as default "local" (not "s3") and returns false without checking S3 connectivity
1.3 WHEN the application attempts to use S3 storage THEN the connection fails because credentials are None/empty

### Expected Behavior (Correct)

2.1 WHEN config.py loads from backend/.env THEN all AWS configuration values SHALL be properly loaded including STORAGE_TYPE, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET, and AWS_REGION
2.2 WHEN STORAGE_TYPE is set to "s3" AND valid AWS credentials are provided THEN the health check SHALL return s3_connected=true
2.3 WHEN STORAGE_TYPE is set to "s3" AND AWS credentials are invalid THEN the health check SHALL log a descriptive error message indicating the specific failure reason

### Unchanged Behavior (Regression Prevention)

3.1 WHEN STORAGE_TYPE is set to "local" THEN the system SHALL CONTINUE TO use local filesystem storage without any S3 connectivity checks
3.2 WHEN STORAGE_TYPE is set to "s3" AND credentials are valid THEN the system SHALL CONTINUE TO upload files to the configured S3 bucket
3.3 WHEN using local storage THEN the health endpoint SHALL CONTINUE TO return s3_connected=false (expected behavior)