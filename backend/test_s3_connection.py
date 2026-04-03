#!/usr/bin/env python3
"""Test AWS S3 connection to diagnose the issue"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Print config
print("=== AWS Configuration ===")
print(f"AWS_ACCESS_KEY_ID: {os.getenv('AWS_ACCESS_KEY_ID')}")
print(f"AWS_SECRET_ACCESS_KEY: {os.getenv('AWS_SECRET_ACCESS_KEY')[:10]}..." if os.getenv('AWS_SECRET_ACCESS_KEY') else "None")
print(f"AWS_S3_BUCKET: {os.getenv('AWS_S3_BUCKET')}")
print(f"AWS_REGION: {os.getenv('AWS_REGION')}")
print(f"STORAGE_TYPE: {os.getenv('STORAGE_TYPE')}")
print()

# Test S3 connection
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

print("=== Testing S3 Connection ===")
try:
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION')
    )
    
    bucket_name = os.getenv('AWS_S3_BUCKET')
    print(f"Attempting to access bucket: {bucket_name}")
    
    # Try to list objects (more informative than head_bucket)
    response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
    print(f"✓ S3 connection successful!")
    print(f"  Response: {response}")
    
except NoCredentialsError as e:
    print(f"✗ NoCredentialsError: {e}")
    print("  -> Credentials not found or invalid")
except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
    error_msg = e.response.get('Error', {}).get('Message', str(e))
    print(f"✗ ClientError: {error_code}")
    print(f"  -> {error_msg}")
    if error_code == 'InvalidAccessKeyId':
        print("  -> The Access Key ID is invalid or doesn't exist")
    elif error_code == 'SignatureDoesNotMatch':
        print("  -> The Secret Access Key doesn't match the signature")
    elif error_code == 'AccessDenied':
        print("  -> Credentials don't have permission to access this bucket")
except EndpointConnectionError as e:
    print(f"✗ EndpointConnectionError: {e}")
    print("  -> Cannot reach the S3 endpoint (network issue or wrong region)")
except Exception as e:
    print(f"✗ Unexpected error: {type(e).__name__}: {e}")