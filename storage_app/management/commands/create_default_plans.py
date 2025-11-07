from django.core.management.base import BaseCommand
from storage_app.models import StoragePlan

class Command(BaseCommand):
    help = 'Create default storage plans'
    
    def handle(self, *args, **options):
        plans = [
            {
                'name': 'Free',
                'plan_type': 'free',
                'max_storage_size': 500 * 1024 * 1024,  # 500MB
                'price': 0,
                'is_active': True,
                'display_order': 0
            },
            {
                'name': 'Basic',
                'plan_type': 'basic',
                'max_storage_size': 5 * 1024 * 1024 * 1024,  # 5GB
                'price': 5,
                'is_active': True,
                'display_order': 1
            },
            {
                'name': 'Professional',
                'plan_type': 'pro',
                'max_storage_size': 50 * 1024 * 1024 * 1024,  # 50GB
                'price': 15,
                'is_active': True,
                'display_order': 2
            },
            {
                'name': 'Enterprise',
                'plan_type': 'enterprise',
                'max_storage_size': 200 * 1024 * 1024 * 1024,  # 200GB
                'price': 50,
                'is_active': True,
                'display_order': 3
            }
        ]
        
        for plan_data in plans:
            plan, created = StoragePlan.objects.get_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created plan: {plan.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Plan already exists: {plan.name}'))