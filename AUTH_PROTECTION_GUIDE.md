# Authentication & Authorization Guide

## Overview
All pages in the frontend and all API endpoints in the backend are now protected with Clerk authentication.

## Frontend Protection

### 🔐 Protected Routes
All routes now require users to be logged in:

- **`/`** (Upload Page) - Protected with `<SignedIn>`
- **`/dashboard`** (Dashboard) - Protected with `<SignedIn>`
- **`/documents/:id`** (Document Detail) - Protected with `<SignedIn>`

### 📝 Public Routes
These routes remain public:

- **`/sign-in`** - Sign in page
- **`/sign-up`** - Sign up page

### 🔐 How Protection Works

All protected routes use the `<SignedIn>` wrapper from Clerk:

```tsx
<Route
  path="/"
  element={
    <SignedIn>
      <UploadPage />
    </SignedIn>
  }
/>
```

If a user is not signed in, they will be redirected to the sign-in page automatically.

### 🔑 API Request Authentication

All API requests now include the Clerk JWT token:

```typescript
instance.interceptors.request.use(async (config) => {
  try {
    const token = await getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch (error) {
    console.error('Failed to get auth token:', error);
  }
  return config;
});
```

## Backend Protection

### 🔐 Protected Endpoints

All API endpoints require authentication via `Depends(get_current_user_id)`:

#### Document Management
- **POST** `/api/v1/documents/upload` - Upload documents (Protected)
- **GET** `/api/v1/documents` - List user's documents (Protected)
- **GET** `/api/v1/documents/{document_id}` - Get document details (Protected)
- **DELETE** `/api/v1/documents/{document_id}` - Delete document (Protected)
- **PUT** `/api/v1/documents/{document_id}/processed-data` - Update processed data (Protected)
- **POST** `/api/v1/documents/{document_id}/finalize` - Finalize document (Protected)

#### Job Management
- **POST** `/api/v1/jobs/{job_id}/retry` - Retry job (Protected)
- **POST** `/api/v1/jobs/{job_id}/cancel` - Cancel job (Protected)
- **GET** `/api/v1/jobs/{job_id}/progress` - Get job progress (Protected)

#### Export
- **GET** `/api/v1/export/json` - Export to JSON (Protected)
- **GET** `/api/v1/export/csv` - Export to CSV (Protected)

#### WebSocket
- **WS** `/api/v1/ws` - WebSocket connection (Protected)

### 🔍 How Authentication Works

1. Client sends request with `Authorization: Bearer <token>` header
2. Backend validates the token with Clerk using `authenticate_request()`
3. If valid, user information is extracted and passed to the endpoint
4. If invalid, a `401 Unauthorized` response is returned

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Validate Clerk JWT token and return user information"""
    # ... validation logic
    auth_state = clerk_client.authenticate_request(mock_request, options)
    
    if not auth_state.is_signed_in:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return user_info
```

## Testing Authentication

### ✅ Test with Frontend
1. Open `http://localhost:5173`
2. You should be redirected to sign-in page
3. Sign up or sign in with Clerk
4. You'll have access to all protected pages
5. All API requests will automatically include your token

### ✅ Test with cURL (Backend)
```bash
# Get your token from Clerk session
# Then use it in requests:

curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/documents
```

## Environment Variables Required

Make sure your `.env` file has valid Clerk credentials:

```env
CLERK_SECRET_KEY=sk_test_...  # Your actual Clerk secret key
```

And frontend has:

```env
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...  # Your actual Clerk publishable key
```

## Error Handling

### 401 Unauthorized
- **Cause**: No token provided or token is invalid
- **Solution**: User needs to sign in again
- **Frontend**: Will show sign-in page

### 403 Forbidden
- **Cause**: Token exists but user doesn't have permission
- **Solution**: Check user permissions

### Token Expiry
- Clerk tokens expire after a period
- Frontend automatically refreshes expired tokens
- If refresh fails, user is logged out

## User Data Protection

Each endpoint verifies the `user_id` from the token matches the document owner:

```python
@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id)  # Verified user
):
    document = await document_service.get_document_by_id(
        document_id, 
        user_id  # Only returns if user is owner
    )
```

This ensures users can only access their own data.

## Troubleshooting

### Issue: "Invalid authentication credentials"
- Check that CLERK_SECRET_KEY is correct
- Verify the token is a valid Clerk JWT
- Ensure the token hasn't expired

### Issue: Frontend shows sign-in after login
- Clear browser cookies
- Check that VITE_CLERK_PUBLISHABLE_KEY is correct
- Ensure Clerk is properly initialized

### Issue: "Unauthorized" errors on every request
- Verify token is being sent in Authorization header
- Check token hasn't expired
- Verify Clerk credentials are correct

## Summary

✅ **Frontend**: All pages except sign-in/sign-up are protected
✅ **Backend**: All API endpoints require valid Clerk JWT token
✅ **User Data**: Each user can only access their own documents
✅ **Security**: Tokens are validated with Clerk on every request
