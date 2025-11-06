from django.db import models
from django.contrib.auth.models import User
import os
import uuid
from django.conf import settings

# Import the custom storage
try:
    from .storage_backends import BackblazeB2Storage
    cloud_storage = BackblazeB2Storage()
except ImportError:
    # Fallback to default S3 storage if custom backend fails
    from storages.backends.s3boto3 import S3Boto3Storage
    cloud_storage = S3Boto3Storage(
        bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL
    )

def user_directory_path(instance, filename):
    return f'user_{instance.owner.id}/{filename}'

class StoragePlan(models.Model):
    name = models.CharField(max_length=100)
    max_storage_size = models.BigIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    storage_plan = models.ForeignKey(StoragePlan, on_delete=models.SET_NULL, null=True)
    used_storage = models.BigIntegerField(default=0)
    
    def get_storage_usage_percent(self):
        if self.storage_plan:
            return (self.used_storage / self.storage_plan.max_storage_size) * 100
        return 0
    
    def __str__(self):
        return f"{self.user.username}'s profile"

class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    parent_folder = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['name', 'owner', 'parent_folder']
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_full_path(self):
        """Get the full folder path"""
        if self.parent_folder:
            return f"{self.parent_folder.get_full_path()}/{self.name}"
        return self.name
    
    def get_files_count(self):
        """Count files in this folder"""
        return self.files.count()
    
    def get_subfolders_count(self):
        """Count subfolders"""
        return self.subfolders.count()

class File(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    file = models.FileField(
        upload_to=user_directory_path,
        storage=cloud_storage
    )
    file_type = models.CharField(max_length=50)
    size = models.BigIntegerField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, null=True, blank=True, related_name='files')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if not self.name:
            self.name = os.path.basename(self.file.name)
        if not self.file_type:
            self.file_type = os.path.splitext(self.file.name)[1].lower()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name

class ShareLink(models.Model):
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Share link for {self.file.name}"