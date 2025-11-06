from django.core.management.base import BaseCommand
from django.conf import settings
from storage_app.models import File
import os

class Command(BaseCommand):
    help = 'Check where files are being stored'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Checking storage configuration...")
        
        # Check settings
        self.stdout.write(f"📁 MEDIA_ROOT: {settings.MEDIA_ROOT}")
        self.stdout.write(f"🌐 DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
        self.stdout.write(f"🔑 AWS_ACCESS_KEY_ID: {'✅ Set' if settings.AWS_ACCESS_KEY_ID else '❌ Not set'}")
        self.stdout.write(f"🪣 AWS_STORAGE_BUCKET_NAME: {settings.AWS_STORAGE_BUCKET_NAME}")
        
        # Check recent files
        recent_files = File.objects.order_by('-uploaded_at')[:10]
        
        self.stdout.write(f"\n📄 Found {recent_files.count()} recent files:")
        
        cloud_count = 0
        local_count = 0
        
        for file in recent_files:
            try:
                # Try to get file URL and check if it's cloud storage
                file_url = file.file.url
                is_cloud = 'backblazeb2.com' in file_url or 'amazonaws.com' in file_url
                
                if is_cloud:
                    cloud_count += 1
                    storage_indicator = "🌐 Cloud"
                else:
                    local_count += 1
                    storage_indicator = "💻 Local"
                
                # Try to get file size
                try:
                    file_size = file.file.size
                    size_str = f"{file_size} bytes"
                except:
                    size_str = "Unknown size"
                
                self.stdout.write(f"   📋 {file.name}")
                self.stdout.write(f"      URL: {file_url}")
                self.stdout.write(f"      Size: {size_str}")
                self.stdout.write(f"      Storage: {storage_indicator}")
                self.stdout.write(f"      Uploaded: {file.uploaded_at}")
                self.stdout.write("")
                
            except Exception as e:
                self.stdout.write(f"   ❌ Error checking file {file.name}: {e}")
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"📊 Storage Summary:"))
        self.stdout.write(f"   🌐 Cloud files: {cloud_count}")
        self.stdout.write(f"   💻 Local files: {local_count}")
        self.stdout.write(f"   📁 Total files: {recent_files.count()}")
        
        if cloud_count > 0:
            self.stdout.write(self.style.SUCCESS("🎉 Cloud storage is working!"))