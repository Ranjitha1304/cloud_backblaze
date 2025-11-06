import os
import boto3
from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Migrate all local files to Backblaze B2 cloud storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-local',
            action='store_true',
            help='Delete local files after successful migration',
        )
        parser.add_argument(
            '--check-only',
            action='store_true', 
            help='Only check configuration without migrating',
        )

    def handle(self, *args, **options):
        
        if options['check_only']:
            self.check_configuration()
            return
            
        self.migrate_files(options['delete_local'])

    def check_configuration(self):
        """Check if Backblaze B2 is properly configured"""
        self.stdout.write("🔧 Checking Backblaze B2 configuration...")
        
        required_settings = {
            'AWS_ACCESS_KEY_ID': settings.AWS_ACCESS_KEY_ID,
            'AWS_SECRET_ACCESS_KEY': settings.AWS_SECRET_ACCESS_KEY,
            'AWS_STORAGE_BUCKET_NAME': getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None),
            'AWS_S3_ENDPOINT_URL': getattr(settings, 'AWS_S3_ENDPOINT_URL', None),
        }
        
        all_configured = True
        for setting_name, setting_value in required_settings.items():
            if setting_value:
                self.stdout.write(self.style.SUCCESS(f"✅ {setting_name}: Configured"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ {setting_name}: Not configured"))
                all_configured = False
        
        if all_configured:
            self.stdout.write(self.style.SUCCESS("🎉 All settings are properly configured!"))
            
            # Test connection
            try:
                client = boto3.client(
                    's3',
                    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
                response = client.list_buckets()
                self.stdout.write(self.style.SUCCESS("✅ Backblaze B2 connection successful!"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Backblaze B2 connection failed: {e}"))
        else:
            self.stdout.write(self.style.WARNING(
                "⚠️  Please configure Backblaze B2 settings in settings.py before migration."
            ))

    def migrate_files(self, delete_local=False):
        """Migrate files to Backblaze B2"""
        # Check if Backblaze is configured
        if not all([
            getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
            getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None),
            getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
        ]):
            self.stdout.write(
                self.style.ERROR('❌ Backblaze B2 not configured. Run with --check-only to see missing settings.')
            )
            return

        client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        local_media = settings.MEDIA_ROOT
        migrated_count = 0
        failed_count = 0
        
        self.stdout.write(f"📁 Scanning local media folder: {local_media}")
        
        # Check if media directory exists
        if not os.path.exists(local_media):
            self.stdout.write(self.style.WARNING(f"⚠️  Media directory {local_media} does not exist."))
            return
        
        for root, dirs, files in os.walk(local_media):
            for file in files:
                local_path = os.path.join(root, file)
                # Create cloud key preserving directory structure
                cloud_key = os.path.relpath(local_path, local_media).replace('\\', '/')
                
                # Skip if file already exists in cloud
                try:
                    client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=cloud_key)
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  Skipped (already exists): {cloud_key}")
                    )
                    continue
                except:
                    pass  # File doesn't exist in cloud, proceed with upload
                
                try:
                    self.stdout.write(f"⬆️  Uploading: {cloud_key}")
                    client.upload_file(local_path, settings.AWS_STORAGE_BUCKET_NAME, cloud_key)
                    migrated_count += 1
                    
                    # Delete local file if requested
                    if delete_local:
                        os.remove(local_path)
                        self.stdout.write(f"🗑️  Deleted local: {cloud_key}")
                    
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Uploaded: {cloud_key}")
                    )
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"❌ Failed: {cloud_key} - {e}")
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"🎉 Migration complete! {migrated_count} files migrated, {failed_count} failed"
            )
        )