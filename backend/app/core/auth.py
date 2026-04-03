from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from typing import Optional

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Simplified user authentication - returns a mock user ID for testing
    TODO: Implement proper Clerk JWT verification
    
    For development, this is optional. In production, verify the JWT token with Clerk.
    """
    try:
        # If no credentials provided, return a default mock user ID (for development)
        if not credentials:
            logger.info("No credentials provided - using mock user ID for development")
            return "dev-user-id"
        
        # If credentials are provided, validate them
        # For now, just return a mock user ID
        # In production, verify the JWT token with Clerk
        return "mock-user-id"
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
