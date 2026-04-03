#!/usr/bin/env python3
"""Debug config loading to find root cause"""
import sys
sys.path.insert(0, '.')

from pathlib import Path

# Check what path config.py is using
config_path = Path("backend/app/core/config.py")
env_file_path = config_path.parent.parent.parent / ".env"
print(f"Config.py loads .env from: {env_file_path}")
print(f"Exists: {env_file_path.exists()}")

# Check what's in that .env
if env_file_path.exists():
    with open(env_file_path) as f:
        content = f.read()
        print(f"\nContents of that .env:")
        for line in content.split('\n')[:10]:
            print(f"  {line}")

# Now check the actual backend/.env
backend_env = Path("backend/.env")
print(f"\n\nbackend/.env exists: {backend_env.exists()}")
if backend_env.exists():
    with open(backend_env) as f:
        content = f.read()
        print(f"Contents of backend/.env (first 10 lines):")
        for line in content.split('\n')[:10]:
            print(f"  {line}")

# Now test what settings actually loads
print("\n\n=== Testing actual settings import ===")
from app.core.config import settings
print(f"STORAGE_TYPE: {settings.STORAGE_TYPE}")
print(f"AWS_ACCESS_KEY_ID: {settings.AWS_ACCESS_KEY_ID}")
print(f"AWS_REGION: {settings.AWS_REGION}")
print(f"AWS_S3_BUCKET: {settings.AWS_S3_BUCKET}")