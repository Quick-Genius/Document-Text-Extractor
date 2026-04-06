# Multi-Document Upload Fix

## Problem
When uploading multiple documents together, all documents get stuck in PENDING status and none of them process.

## Root Cause
**Celery worker concurrency was set to 1**, meaning only ONE task could process at a time. When multiple documents were uploaded:
1. All tasks were enqueued successfully
2. Worker picked up first task
3. Other tasks waited in queue
4. If first task took long or got stuck, all others remained PENDING

## Solution
Changed `worker_concurrency` from 1 to 4 in `backend/app/workers/celery_app.py`:

```python
worker_concurrency=4,  # Allow 4 concurrent tasks (was 1)
```

This allows up to 4 documents to process simultaneously.

## Additional Fixes Applied

### 1. Removed Live Preview Feature
- Removed all preview-related code from `DocumentDetail.tsx`
- Removed preview state management
- Removed preview UI card
- Cleaned up unused imports

**Why**: Preview feature had persistent CORS issues and wasn't critical for core functionality.

### 2. Celery Task Cleanup
- Ran cleanup endpoint which found and revoked 2 stale tasks
- These were likely from previous failed uploads

## Files Modified
1. `backend/app/workers/celery_app.py` - Increased worker concurrency to 4
2. `frontend/src/components/detail/DocumentDetail.tsx` - Removed live preview feature

## Testing

### Before Fix
```bash
# Upload 3 documents
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@doc3.pdf"

# Result: All 3 stuck in PENDING, only first one processes
```

### After Fix
```bash
# Upload 3 documents
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@doc3.pdf"

# Result: All 3 process concurrently (up to 4 at once)
```

## Deployment

### 1. Restart Celery Worker (REQUIRED)
```bash
cd backend
# Stop current worker (Ctrl+C)
celery -A app.workers.celery_app worker --loglevel=info
```

The new concurrency setting will take effect immediately.

### 2. Clean Up Stale Tasks (Optional)
```bash
curl http://localhost:8000/api/v1/admin/cleanup-tasks
```

### 3. Verify Worker Concurrency
Check Celery worker startup logs for:
```
concurrency: 4 (prefork)
```

## Performance Considerations

### Concurrency = 4
- **Pros**: 
  - 4 documents process simultaneously
  - Much faster for batch uploads
  - Better resource utilization
- **Cons**:
  - Higher memory usage (4x)
  - Higher CPU usage
  - More database connections

### Adjusting Concurrency
If you need different concurrency:

```python
# For more concurrent processing (if server has resources)
worker_concurrency=8,

# For less concurrent processing (if server is constrained)
worker_concurrency=2,
```

## Monitoring

### Check Active Tasks
```bash
celery -A app.workers.celery_app inspect active
```

### Check Queue Length
```bash
celery -A app.workers.celery_app inspect reserved
```

### Check Worker Stats
```bash
celery -A app.workers.celery_app inspect stats
```

## Expected Behavior Now

1. **Single Upload**: Processes immediately
2. **Batch Upload (2-4 docs)**: All process concurrently
3. **Batch Upload (5+ docs)**: First 4 process, others queue and process as slots free
4. **Large Batch (10 docs)**: Processes in waves of 4

## Additional Notes

- `worker_prefetch_multiplier=1` ensures fair distribution (no task hoarding)
- `task_acks_late=True` ensures tasks aren't lost if worker crashes
- `worker_max_tasks_per_child=100` prevents memory leaks from long-running workers

## Future Improvements

1. **Auto-scaling**: Add more workers based on queue depth
2. **Priority Queue**: Process smaller files first
3. **Progress Tracking**: Real-time updates for batch uploads
4. **Retry Logic**: Automatic retry for failed tasks
