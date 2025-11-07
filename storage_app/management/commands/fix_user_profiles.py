from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from storage_app.models import UserProfile, StoragePlan

class Command(BaseCommand):
    help = 'Fix missing UserProfiles and assign default free plan'
    
    def handle(self, *args, **options):
        # Get or create the free plan
        free_plan, created = StoragePlan.objects.get_or_create(
            name="Free",
            defaults={
                'max_storage_size': 500 * 1024 * 1024,
                'price': 0,
                'plan_type': 'free',
                'is_active': True
            }
        )
        
        # Fix all users
        users = User.objects.all()
        fixed_count = 0
        
        for user in users:
            try:
                # Try to get existing profile
                profile = UserProfile.objects.get(user=user)
                # If profile exists but has no plan, assign free plan
                if not profile.storage_plan:
                    profile.storage_plan = free_plan
                    profile.save()
                    fixed_count += 1
                    self.stdout.write(f'Fixed plan for user: {user.username}')
                    
            except UserProfile.DoesNotExist:
                # Create missing profile
                UserProfile.objects.create(
                    user=user,
                    storage_plan=free_plan,
                    used_storage=0
                )
                fixed_count += 1
                self.stdout.write(f'Created profile for user: {user.username}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully fixed {fixed_count} user profiles!')
        )