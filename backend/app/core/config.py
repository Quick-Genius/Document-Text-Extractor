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
    
    # RabbitMQ
    RABBITMQ_URL: Optional[str] = None
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    @model_validator(mode='after')
    def assemble_worker_urls(self) -> 'Settings':
        # Construct RabbitMQ URL if not provided
        rabbitmq_url = self.RABBITMQ_URL
        if not rabbitmq_url:
            rabbitmq_url = (
                f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
                f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"
            )
        
        # Construct Redis URL if not provided
        redis_base_url = self.REDIS_URL
        if not redis_base_url:
            if self.REDIS_PASSWORD:
                redis_base_url = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            else:
                redis_base_url = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        
        # Set CELERY_BROKER_URL to RabbitMQ and CELERY_RESULT_BACKEND to Redis
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = rabbitmq_url
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
    
    # Concurrency Controls (for deadlock fix)
    PRISMA_POOL_SIZE: int = 20
    PRISMA_POOL_TIMEOUT: int = 30
    PRISMA_OPERATION_TIMEOUT: int = 10
    TASK_TOTAL_TIMEOUT: int = 900  # 15 minutes
    BATCH_UPLOAD_MAX_QUEUE_DEPTH: int = 50
    BATCH_UPLOAD_MAX_CONCURRENT_TASKS: int = 5
    
    # Task Enqueue Retry Configuration (for batch upload task enqueue fix)
    TASK_ENQUEUE_MAX_RETRIES: int = 3  # Number of retry attempts for task enqueuing
    TASK_ENQUEUE_RETRY_DELAY: int = 1  # Delay between retry attempts in seconds (exponential backoff applied)
    
    # Scheduler Configuration (for automatic task scheduler)
    SCHEDULER_HEALTH_CHECK_INTERVAL: int = 20  # Seconds between health checks
    SCHEDULER_MAX_CONCURRENCY: int = 4  # Maximum concurrent processing tasks
    SCHEDULER_STUCK_THRESHOLD: int = 300  # Seconds before document considered stuck (5 minutes)
    SCHEDULER_QUEUE_WARNING: int = 20  # Queue depth warning threshold
    SCHEDULER_QUEUE_ERROR: int = 50  # Queue depth error threshold
    
    @field_validator("SCHEDULER_HEALTH_CHECK_INTERVAL")
    @classmethod
    def validate_health_check_interval(cls, v: int) -> int:
        if v < 5 or v > 300:
            raise ValueError("SCHEDULER_HEALTH_CHECK_INTERVAL must be between 5 and 300 seconds")
        return v
    
    @field_validator("SCHEDULER_MAX_CONCURRENCY")
    @classmethod
    def validate_max_concurrency(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("SCHEDULER_MAX_CONCURRENCY must be between 1 and 20")
        return v
    
    @field_validator("SCHEDULER_STUCK_THRESHOLD")
    @classmethod
    def validate_stuck_threshold(cls, v: int) -> int:
        if v < 60:
            raise ValueError("SCHEDULER_STUCK_THRESHOLD must be at least 60 seconds")
        return v
    
    @field_validator("SCHEDULER_QUEUE_WARNING")
    @classmethod
    def validate_queue_warning(cls, v: int) -> int:
        if v < 1:
            raise ValueError("SCHEDULER_QUEUE_WARNING must be at least 1")
        return v
    
    @field_validator("SCHEDULER_QUEUE_ERROR")
    @classmethod
    def validate_queue_error(cls, v: int) -> int:
        if v < 1:
            raise ValueError("SCHEDULER_QUEUE_ERROR must be at least 1")
        return v
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
