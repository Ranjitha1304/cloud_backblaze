from django.core.management.base import BaseCommand
from storage_app.models import StoragePlan

class Command(BaseCommand):
    help = 'Create initial storage plans'

    def handle(self, *args, **options):
        plans = [
            {'name': 'Free', 'max_storage_size': 500 * 1024 * 1024, 'price': 0},
            {'name': 'Basic', 'max_storage_size': 5 * 1024 * 1024 * 1024, 'price': 4.99},
            {'name': 'Pro', 'max_storage_size': 50 * 1024 * 1024 * 1024, 'price': 14.99},
            {'name': 'Enterprise', 'max_storage_size': 500 * 1024 * 1024 * 1024, 'price': 49.99},
        ]
        
        for plan_data in plans:
            plan, created = StoragePlan.objects.get_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created {plan.name} plan')
                )