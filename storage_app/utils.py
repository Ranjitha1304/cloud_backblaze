import boto3
from django.conf import settings

def check_storage_usage():
    """Check current storage usage to avoid surprise costs"""
    client = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    
    # Calculate total storage used
    paginator = client.get_paginator('list_objects_v2')
    total_size = 0
    file_count = 0
    
    for page in paginator.paginate(Bucket=settings.AWS_STORAGE_BUCKET_NAME):
        if 'Contents' in page:
            for obj in page['Contents']:
                total_size += obj['Size']
                file_count += 1
    
    return {
        'total_size_gb': total_size / (1024 ** 3),
        'file_count': file_count,
        'free_tier_remaining': max(0, 10 - (total_size / (1024 ** 3)))  # 10GB free
    }