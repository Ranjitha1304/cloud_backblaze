from django.core.management.base import BaseCommand
from storage_app.models import File, ShareLink
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Debug share functionality'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Check existing share links
        share_links = ShareLink.objects.all()
        self.stdout.write(f"📋 Found {share_links.count()} share links:")
        
        for sl in share_links:
            self.stdout.write(f"   🔗 {sl.token} -> {sl.file.name} (Active: {sl.is_active})")
        
        # Test creating a new share link
        user = User.objects.first()
        if user:
            file = File.objects.filter(owner=user).first()
            if file:
                self.stdout.write(f"\n🧪 Testing share for file: {file.name}")
                self.stdout.write(f"   File URL: {file.file.url}")
                self.stdout.write(f"   File is_public: {file.is_public}")