"""
Database connection pool manager for Prisma.

For Celery tasks, Prisma Python client manages connections internally.
We configure connection pooling via DATABASE_URL parameters and ensure
proper connection reuse within task contexts.
"""
from prisma import Prisma
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_prisma_with_pool() -> Prisma:
    """
    Get a Prisma client configured for connection pooling.
    
    Prisma Python client manages connection pooling internally via the
    PostgreSQL connection string. We ensure proper configuration through
    DATABASE_URL parameters.
    
    For optimal connection pooling:
    - Use connection_limit parameter in DATABASE_URL
    - Reuse the same Prisma instance within a task/request context
    - Always disconnect when done to return connections to the pool
    
    Returns:
        Prisma: A new Prisma client instance
    """
    # Prisma Python client will use the DATABASE_URL from environment
    # Connection pooling is managed by the underlying PostgreSQL driver
    # Pool size is controlled by connection_limit in DATABASE_URL or
    # by PostgreSQL's max_connections setting
    return Prisma()


async def connect_prisma_with_timeout(db: Prisma, timeout: int = 30):
    """
    Connect to Prisma with timeout protection.
    
    Args:
        db: Prisma client instance
        timeout: Connection timeout in seconds
    
    Raises:
        Exception: If connection times out or fails
    """
    import asyncio
    import sys
    
    # Patch stdio for Prisma subprocess
    original_stdout, original_stderr = sys.stdout, sys.stderr
    try:
        if not hasattr(sys.stdout, "fileno"):
            sys.stdout = sys.__stdout__
        if not hasattr(sys.stderr, "fileno"):
            sys.stderr = sys.__stderr__
        
        # Connect with timeout
        await asyncio.wait_for(db.connect(), timeout=timeout)
        
    except asyncio.TimeoutError:
        raise Exception(f"Database connection timeout after {timeout}s")
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr


async def disconnect_prisma_with_timeout(db: Prisma, timeout: int = 10):
    """
    Disconnect from Prisma with timeout protection.
    
    Args:
        db: Prisma client instance
        timeout: Disconnection timeout in seconds
    """
    import asyncio
    
    try:
        await asyncio.wait_for(db.disconnect(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Database disconnection timeout after {timeout}s")
    except Exception as e:
        logger.warning(f"Database disconnection error: {e}")
