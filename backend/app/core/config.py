from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import List, Union, Optional, Any
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file at module import time
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

class Settings(BaseSettings):
    # Application
    DEBUG: bool = False
    APP_NAME: str = "Document Processing API"
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:5174"
    
    # CORS
    # Accepts comma-separated string or JSON-style list
    CORS_ORIGINS: Any = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return v
    
    # Database - Neon supports both pooled and direct connections
    # DATABASE_URL can be either:
    # - Pooled (pgBouncer): postgresql://user:pass@....-pooler.neon.tech/dbname
    # - Direct: postgresql://user:pass@....neon.tech/dbname
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/docproc"
    DATABASE_URL_POOLED: Optional[str] = None  # Neon pooled connection (for serverless/frequent connections)
    DATABASE_URL_DIRECT: Optional[str] = None  # Neon direct connection (for long-running processes)
    
    # Redis
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    @model_validator(mode='after')
    def assemble_worker_urls(self) -> 'Settings':
        # Use REDIS_URL if provided, otherwise construct from individual components
        redis_base_url = self.REDIS_URL
        if not redis_base_url:
            if self.REDIS_PASSWORD:
                redis_base_url = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            else:
                redis_base_url = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = redis_base_url
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = redis_base_url
        
        # Neon DB URL selection: prefer pooled for serverless, direct for long-running
        # Default to DATABASE_URL, but allow override via environment-specific URLs
        if self.DATABASE_URL_POOLED:
            self.DATABASE_URL = self.DATABASE_URL_POOLED
        elif self.DATABASE_URL_DIRECT:
            self.DATABASE_URL = self.DATABASE_URL_DIRECT
        
        return self

    # Clerk Authentication
    CLERK_SECRET_KEY: str = ""
    CLERK_FRONTEND_API: str = ""
    
    # File Storage
    STORAGE_TYPE: str = "local"  # "local" or "s3"
    LOCAL_STORAGE_PATH: str = "/app/storage"
    
    # AWS S3 (if STORAGE_TYPE = "s3")
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    
    # File Upload Limits
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_FILES_PER_UPLOAD: int = 10
    
    # Processing
    TASK_TIMEOUT: int = 1800  # 30 minutes
    MAX_RETRIES: int = 3
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
