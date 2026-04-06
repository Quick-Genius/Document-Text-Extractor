# Batch Upload Deadlock Tests

## Overview

This directory contains property-based tests for the document processing deadlock fix.

## Test Files

### 1. `test_batch_upload_deadlock.py`
**Purpose**: Comprehensive property-based test using Hypothesis  
**Validates**: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8  
**Features**:
- Property-based testing with Hypothesis
- Tests batch sizes from 2-10 documents
- Tests multiple file types (txt, pdf)
- Generates multiple test cases automatically
- Includes connection pool exhaustion test

**Usage**:
```bash
# Run all property-based tests
pytest tests/test_batch_upload_deadlock.py -v -s --log-cli-level=INFO

# Run specific test
pytest tests/test_batch_upload_deadlock.py::test_batch_upload_deadlock_bug_condition -v -s
```

### 2. `test_batch_upload_deadlock_simple.py`
**Purpose**: Fast, simple test case for quick validation  
**Validates**: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8  
**Features**:
- Single test case with 3 documents
- 60-second timeout for faster execution
- Detailed logging of deadlock symptoms
- Clear counterexample documentation

**Usage**:
```bash
pytest tests/test_batch_upload_deadlock_simple.py -v -s --log-cli-level=INFO
```

### 3. `DEADLOCK_BUG_EVIDENCE.md`
**Purpose**: Documentation of bug evidence and counterexamples  
**Contents**:
- Detailed counterexamples from test execution
- Celery worker log excerpts
- Root cause analysis
- Confirmation of all 8 bug conditions

## Test Execution Requirements

### Prerequisites
1. **Celery Worker Running**:
   ```bash
   cd backend
   celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
   ```

2. **Dependencies Installed**:
   ```bash
   pip install hypothesis pytest-asyncio
   ```

3. **Environment Variables**:
   - `DATABASE_URL` - PostgreSQL connection string
   - `REDIS_URL` - Redis connection string
   - `CELERY_BROKER_URL` - Celery broker (auto-configured from REDIS_URL)

### Running Tests

**Important**: These tests are designed to FAIL on unfixed code. This is expected behavior!

```bash
# Start Celery worker in one terminal
cd backend
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

# Run tests in another terminal
cd backend
pytest tests/test_batch_upload_deadlock_simple.py -v -s --log-cli-level=INFO
```

## Expected Outcomes

### On UNFIXED Code (Current State)
**Expected**: Tests FAIL ✓  
**Reason**: Confirms the bug exists

**Symptoms**:
- Documents stuck in PENDING status
- Redis connection errors (Broken pipe)
- PostgreSQL connection errors
- Worker threads blocked
- System overload

### On FIXED Code (After Implementation)
**Expected**: Tests PASS ✓  
**Reason**: Confirms the fix works

**Behavior**:
- All documents complete successfully
- No connection errors
- Proper concurrency controls
- No deadlocks or blocking

## Bug Condition

The tests verify the bug condition:

```python
isBugCondition(input) = (
    input.documentCount >= 2 AND
    (noTransactionIsolation() OR
     noConnectionPooling() OR
     noDatabaseLocking() OR
     redisSingletonUsed() OR
     noTaskCoordination() OR
     noCheckpointValidation() OR
     noOperationTimeouts() OR
     noRateLimiting())
)
```

## Counterexamples Found

See `DEADLOCK_BUG_EVIDENCE.md` for detailed counterexamples including:

1. Documents stuck in PENDING (1.1, 1.5, 1.6)
2. Redis connection errors (1.4)
3. PostgreSQL connection errors (1.2, 1.7)
4. Lost job status updates (1.3)
5. Worker thread blocking (1.6, 1.7)
6. System overload (1.8)

## Next Steps

1. **Implement Fixes** (Tasks 3.1-3.9):
   - Add configuration parameters
   - Implement transaction isolation
   - Add connection pooling
   - Implement database locking
   - Verify task-scoped Redis
   - Add distributed locking
   - Implement checkpoint validation
   - Add operation timeouts
   - Implement rate limiting

2. **Re-run Tests**:
   - Tests should PASS after fixes
   - Verify no regressions

3. **Run Preservation Tests** (Task 2):
   - Verify single document uploads still work
   - Verify sequential processing still works
