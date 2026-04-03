#!/usr/bin/env python3
"""Test script to verify config.py loads AWS credentials from backend/.env"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Reload the config module to pick up the fix
if 'backend.app.core.config' in sys.modules:
    del sys.modules['backend.app.core.config']
if 'app.core.config' in sys.modules:
    del sys.modules['app.core.config']

# Import and check
from app.core.config import settings

print("=== Config Values After Fix ===")
print(f"STORAGE_TYPE: {settings.STORAGE_TYPE}")
print(f"AWS_ACCESS_KEY_ID: {settings.AWS_ACCESS_KEY_ID}")
print(f"AWS_SECRET_ACCESS_KEY: {settings.AWS_SECRET_ACCESS_KEY}")
print(f"AWS_S3_BUCKET: {settings.AWS_S3_BUCKET}")
print(f"AWS_REGION: {settings.AWS_REGION}")
print(f"DATABASE_URL: {settings.DATABASE_URL[:50]}...")
print(f"REDIS_URL: {settings.REDIS_URL}")

# Verify AWS credentials are loaded
assert settings.STORAGE_TYPE == "local", f"Expected STORAGE_TYPE='local', got '{settings.STORAGE_TYPE}'"
assert settings.AWS_ACCESS_KEY_ID is not None, "AWS_ACCESS_KEY_ID should not be None"
assert settings.AWS_SECRET_ACCESS_KEY is not None, "AWS_SECRET_ACCESS_KEY should not be None"
assert settings.AWS_S3_BUCKET is not None, "AWS_S3_BUCKET should not be None"
assert settings.AWS_REGION == "us-east-1", f"Expected AWS_REGION='us-east-1', got '{settings.AWS_REGION}'"

print("\n=== All AWS credentials loaded successfully! ===")