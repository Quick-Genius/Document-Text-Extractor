from abc import ABC, abstractmethod
from fastapi import UploadFile
import aiofiles
import os
from app.core.config import settings
import boto3
from botocore.exceptions import NoCredentialsError
import logging

logger = logging.getLogger(__name__)

class StorageBackend(ABC):
    @abstractmethod
    async def save_file(self, file: UploadFile, filename: str, folder: str) -> str:
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> None:
        pass

class LocalStorageBackend(StorageBackend):
    def __init__(self):
        self.base_path = settings.LOCAL_STORAGE_PATH
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

    async def save_file(self, file: UploadFile, filename: str, folder: str) -> str:
        folder_path = os.path.join(self.base_path, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        file_path = os.path.join(folder_path, filename)
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        return file_path

    async def delete_file(self, file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)

import asyncio
from functools import partial

class S3StorageBackend(StorageBackend):
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.AWS_S3_BUCKET

    async def save_file(self, file: UploadFile, filename: str, folder: str) -> str:
        try:
            content = await file.read()
            key = f"{folder}/{filename}"
            
            loop = asyncio.get_event_loop()
            func = partial(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                ContentType=file.content_type
            )
            await loop.run_in_executor(None, func)
            
            # Return the S3 URL
            return f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
        except NoCredentialsError:
            logger.error("AWS credentials not available")
            raise Exception("AWS credentials not configured")
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise Exception(f"Failed to upload to S3: {e}")

    async def delete_file(self, file_path: str) -> None:
        try:
            # Extract key from S3 URL
            if "amazonaws.com/" in file_path:
                key = file_path.split("amazonaws.com/")[1]
                loop = asyncio.get_event_loop()
                func = partial(self.s3_client.delete_object, Bucket=self.bucket_name, Key=key)
                await loop.run_in_executor(None, func)
        except Exception as e:
            logger.error(f"S3 delete failed: {e}")

class StorageService:
    def __init__(self):
        if settings.STORAGE_TYPE == 'local':
            self.backend = LocalStorageBackend()
        elif settings.STORAGE_TYPE == 's3':
            self.backend = S3StorageBackend()
        else:
            raise NotImplementedError(f"Storage type '{settings.STORAGE_TYPE}' is not supported")

    async def save_file(self, file: UploadFile, filename: str, folder: str) -> str:
        return await self.backend.save_file(file, filename, folder)

    async def delete_file(self, file_path: str) -> None:
        await self.backend.delete_file(file_path)
