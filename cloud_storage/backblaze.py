import boto3
from django.conf import settings

def get_b2_client():
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )

def test_connection():
    """Test if Backblaze B2 connection works"""
    try:
        client = get_b2_client()
        response = client.list_buckets()
        print("✅ Backblaze B2 connection successful!")
        print(f"📦 Available buckets: {[b['Name'] for b in response['Buckets']]}")
        return True
    except Exception as e:
        print(f"❌ Backblaze B2 connection failed: {e}")
        return False