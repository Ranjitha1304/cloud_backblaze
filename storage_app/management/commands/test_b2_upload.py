import boto3
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from storage_app.models import File, User
from django.conf import settings

class Command(BaseCommand):
    help = 'Test direct upload to Backblaze B2'

    def handle(self, *args, **options):
        self.stdout.write("🧪 Testing Backblaze B2 upload...")
        
        # Test 1: Check boto3 connection
        self.stdout.write("1. Testing boto3 connection...")
        try:
            client = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            client.list_buckets()
            self.stdout.write(self.style.SUCCESS("   ✅ boto3 connection works"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ boto3 connection failed: {e}"))
            return

        # Test 2: Check Django storage
        self.stdout.write("2. Testing Django storage backend...")
        try:
            from storages.backends.s3boto3 import S3Boto3Storage
            storage = S3Boto3Storage(
                bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
                endpoint_url=settings.AWS_S3_ENDPOINT_URL
            )
            self.stdout.write(self.style.SUCCESS(f"   ✅ Storage backend: {storage.__class__}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Storage backend failed: {e}"))

        # Test 3: Upload a test file
        self.stdout.write("3. Testing file upload through Django...")
        user = User.objects.first()
        if user:
            try:
                test_content = b"Test file for Backblaze B2 upload"
                test_file = ContentFile(test_content)
                test_file.name = "test_b2_upload.txt"
                
                file_obj = File(
                    name=test_file.name,
                    file_type=".txt", 
                    size=len(test_content),
                    owner=user
                )
                file_obj.file.save(test_file.name, test_file)
                file_obj.save()
                
                self.stdout.write(self.style.SUCCESS("   ✅ File upload successful!"))
                self.stdout.write(f"   📁 File URL: {file_obj.file.url}")
                self.stdout.write(f"   🔍 Storage: {file_obj.file.storage.__class__}")
                
                # Check if it's really in cloud
                if 'backblazeb2.com' in file_obj.file.url:
                    self.stdout.write(self.style.SUCCESS("   🌐 File is in Backblaze B2!"))
                else:
                    self.stdout.write(self.style.WARNING("   ⚠️ File might not be in Backblaze B2"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ File upload failed: {e}"))
        else:
            self.stdout.write(self.style.WARNING("   ⚠️ No user found for test"))