# AWS S3 Connection Fix Design

## Overview

The AWS S3 connection health check returns `s3_connected: false` even when valid AWS credentials are configured. The root cause is that `backend/app/core/config.py` loads environment variables from the project root `.env` instead of `backend/.env` where the AWS credentials are defined. The fix involves updating the `.env` file path in config.py to point to the correct location.

## Glossary

- **Bug_Condition (C)**: When config.py loads from the wrong .env path (project root instead of backend/.env), AWS credentials are not loaded
- **Property (P)**: When STORAGE_TYPE=s3 and valid credentials exist, S3 connection should succeed
- **Preservation**: Local storage behavior must remain unchanged when STORAGE_TYPE=local
- **Settings**: The pydantic Settings class in `backend/app/core/config.py` that loads environment variables
- **load_dotenv**: Python function that loads .env file into environment variables

## Bug Details

### Bug Condition

The bug manifests when the application starts and config.py attempts to load environment variables. The Settings class loads from the wrong .env file path, causing AWS credentials to be missing.

**Formal Specification:**
```
FUNCTION isBugCondition()
  OUTPUT: boolean
  
  RETURN settings.STORAGE_TYPE != "s3"
         OR settings.AWS_ACCESS_KEY IS NULL
         OR settings.AWS_SECRET_ACCESS_KEY IS NULL
         OR settings.AWS_S3_BUCKET IS NULL
END FUNCTION
```

### Examples

- **Current Behavior**: When app starts, STORAGE_TYPE defaults to "local" (not "s3"), AWS_ACCESS_KEY_ID is None, AWS_SECRET_ACCESS_KEY is None, AWS_S3_BUCKET is None
- **Expected Behavior**: When app starts with backend/.env, STORAGE_TYPE should be "s3", AWS credentials should be loaded from backend/.env
- **Root Cause**: config.py line 10 uses `Path(__file__).parent.parent.parent / ".env"` which resolves to project root `.env` instead of `backend/.env`

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Local storage (STORAGE_TYPE=local) must continue to work without S3 connectivity checks
- When STORAGE_TYPE=s3 with valid credentials, files must upload to S3 bucket
- Health endpoint must return s3_connected=false for local storage (expected behavior)
- All other application functionality must remain unchanged

**Scope:**
All inputs that do NOT involve S3 configuration should be completely unaffected by this fix. This includes:
- Database connections (Neon PostgreSQL)
- Redis connections
- Clerk authentication
- File processing workers

## Hypothesized Root Cause

Based on the code analysis, the issue is clear:

1. **Incorrect .env Path**: config.py line 10 uses `Path(__file__).parent.parent.parent / ".env"` which resolves to project root `./.env`
   - `__file__` = `backend/app/core/config.py`
   - `.parent.parent.parent` = project root (3 levels up)
   - This loads `.env` which only contains database/redis config, NOT AWS credentials

2. **AWS Credentials Location**: All AWS credentials are defined in `backend/.env`:
   - STORAGE_TYPE=local (should be s3)
   - AWS_ACCESS_KEY_ID="YOUR_AWS_ACCESS_KEY_ID"
   - AWS_SECRET_ACCESS_KEY="YOUR_AWS_SECRET_ACCESS_KEY"
   - AWS_S3_BUCKET="assesmentbucket74408"
   - AWS_REGION="us-east-1"

3. **Missing AWS Credentials**: Because the wrong .env is loaded, all AWS settings remain at their default values (None for optional fields, "local" for STORAGE_TYPE)

## Correctness Properties

Property 1: Bug Condition - AWS Credentials Loading

_For any_ application startup where config.py loads from the correct .env path (backend/.env), the Settings class SHALL load all AWS configuration values including STORAGE_TYPE, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET, and AWS_REGION with their configured values.

**Validates: Requirements 2.1**

Property 2: Preservation - Local Storage Behavior

_For any_ application startup where STORAGE_TYPE is set to "local" (either from config or default), the system SHALL continue to use local filesystem storage without attempting S3 connectivity, and the health endpoint SHALL return s3_connected=false.

**Validates: Requirements 3.1, 3.2, 3.3**

## Fix Implementation

### Changes Required

**File**: `backend/app/core/config.py`

**Function**: Module-level .env loading (lines 9-11)

**Specific Changes**:
1. **Fix .env Path**: Change line 10 from:
   ```python
   env_file = Path(__file__).parent.parent.parent / ".env"
   ```
   to:
   ```python
   env_file = Path(__file__).parent.parent / ".env"
   ```
   
   This changes the path resolution from 3 levels up (project root) to 2 levels up (backend directory).

2. **Alternative Fix**: Use absolute path or environment-based path:
   ```python
   # Option A: Relative to project root
   env_file = Path(__file__).parent.parent.parent / "backend" / ".env"
   
   # Option B: Use environment variable for flexibility
   env_file = Path(os.getenv("ENV_FILE_PATH", Path(__file__).parent.parent / ".env"))
   ```

3. **Update STORAGE_TYPE in backend/.env** (if needed): The current value is `local`, should be `s3` for testing

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, verify the current broken behavior, then verify the fix works correctly.

### Exploratory Bug Condition Checking

**Goal**: Confirm the bug exists by checking current config values before fix.

**Test Plan**: Add debug logging or test script to print loaded config values. Run on UNFIXED code to observe:
- STORAGE_TYPE defaults to "local" (not loaded from backend/.env)
- AWS_ACCESS_KEY_ID is None
- AWS_SECRET_ACCESS_KEY is None
- AWS_S3_BUCKET is None

**Expected Counterexamples**:
- All AWS settings show default/None values despite being in backend/.env

### Fix Checking

**Goal**: Verify that after the fix, all AWS configuration values are properly loaded.

**Pseudocode:**
```
FOR ALL config values DO
  result := load_config()
  ASSERT result.STORAGE_TYPE == "s3"  # or whatever is in backend/.env
  ASSERT result.AWS_ACCESS_KEY_ID is not None
  ASSERT result.AWS_SECRET_ACCESS_KEY is not None
  ASSERT result.AWS_S3_BUCKET is not None
END FOR
```

### Preservation Checking

**Goal**: Verify that local storage behavior remains unchanged.

**Pseudocode:**
```
FOR ALL non-S3 configs DO
  result := load_config()
  ASSERT result.DATABASE_URL is not None
  ASSERT result.REDIS_URL is not None
  ASSERT result.CLERK_SECRET_KEY is not None
END FOR
```

**Test Cases**:
1. **Config Loading Test**: Verify AWS values load from backend/.env after fix
2. **Local Storage Preservation**: Verify local storage still works when STORAGE_TYPE=local
3. **Database Config Preservation**: Verify DATABASE_URL loads correctly
4. **Redis Config Preservation**: Verify REDIS_URL loads correctly

### Unit Tests

- Test config.py module import loads correct .env file
- Test Settings class has correct AWS values
- Test that missing .env file doesn't crash (graceful fallback)

### Property-Based Tests

- Generate random valid .env configurations and verify loading works
- Test path resolution works across different project structures

### Integration Tests

- Test health endpoint returns s3_connected=true when STORAGE_TYPE=s3 with valid credentials
- Test file upload to S3 works when properly configured
- Test local storage continues to work after fix