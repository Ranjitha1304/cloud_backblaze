from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings

class BackblazeB2Storage(S3Boto3Storage):
    """Custom storage backend for Backblaze B2"""
    
    def __init__(self, *args, **kwargs):
        # Explicitly set all Backblaze B2 settings
        super().__init__(
            bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
            access_key=settings.AWS_ACCESS_KEY_ID,
            secret_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            file_overwrite=settings.AWS_S3_FILE_OVERWRITE,
            default_acl=settings.AWS_DEFAULT_ACL,
            querystring_auth=settings.AWS_QUERYSTRING_AUTH,
            *args, **kwargs
        )