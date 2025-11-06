# storage_app/management/commands/debug_file_locations.py
from django.core.management.base import BaseCommand
from storage_app.models import File
import boto3
from django.conf import settings

class Command(BaseCommand):
    help = 'Debug file locations in Backblaze B2'

    def handle(self, *args, **options):
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        # Get all files from database
        files = File.objects.all()[:5]
        
        self.stdout.write("🔍 Checking file locations:")
        
        for file_obj in files:
            self.stdout.write(f"\n📁 File: {file_obj.name}")
            self.stdout.write(f"   Database file.name: {file_obj.file.name}")
            self.stdout.write(f"   Database file.url: {file_obj.file.url}")
            
            # Try to list files in Backblaze to see the actual structure
            try:
                # List objects with prefix
                prefix = file_obj.file.name.split('/')[0] if '/' in file_obj.file.name else ''
                response = s3_client.list_objects_v2(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Prefix=prefix,
                    MaxKeys=10
                )
                
                if 'Contents' in response:
                    self.stdout.write("   📋 Files found in Backblaze:")
                    for obj in response['Contents']:
                        self.stdout.write(f"      - {obj['Key']} ({obj['Size']} bytes)")
                else:
                    self.stdout.write("   ❌ No files found with this prefix")
                    
            except Exception as e:
                self.stdout.write(f"   ❌ Error listing files: {e}")

        # Check bucket contents
        self.stdout.write(f"\n🪣 Bucket contents overview:")
        try:
            response = s3_client.list_objects_v2(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                MaxKeys=20
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    self.stdout.write(f"   - {obj['Key']}")
            else:
                self.stdout.write("   ℹ️ Bucket is empty")
                
        except Exception as e:
            self.stdout.write(f"   ❌ Error listing bucket: {e}")