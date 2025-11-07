from django.core.management.base import BaseCommand
from storage_app.models import StoragePlan
import stripe
from django.conf import settings

class Command(BaseCommand):
    help = 'Setup default payment plans in Stripe and database'
    
    def handle(self, *args, **options):
        # Initialize Stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        plans_data = [
            {
                'name': 'Free',
                'plan_type': 'free',
                'max_storage_size': 500 * 1024 * 1024,  # 500MB
                'price': 0,
                'billing_period': 'monthly',
                'features': [
                    '500MB Storage',
                    'Basic File Sharing',
                    'Standard Support',
                    '100MB File Size Limit'
                ],
                'display_order': 0
            },
            {
                'name': 'Basic',
                'plan_type': 'basic',
                'max_storage_size': 5 * 1024 * 1024 * 1024,  # 5GB
                'price': 5,
                'billing_period': 'monthly',
                'features': [
                    '5GB Storage',
                    'Advanced File Sharing',
                    'Priority Support',
                    '2GB File Size Limit',
                    'No Ads'
                ],
                'display_order': 1
            },
            {
                'name': 'Professional',
                'plan_type': 'pro',
                'max_storage_size': 50 * 1024 * 1024 * 1024,  # 50GB
                'price': 15,
                'billing_period': 'monthly',
                'features': [
                    '50GB Storage',
                    'Advanced File Sharing',
                    'Priority Support',
                    '2GB File Size Limit',
                    'No Ads',
                    'Advanced Analytics',
                    'Custom Branding'
                ],
                'display_order': 2
            },
            {
                'name': 'Enterprise',
                'plan_type': 'enterprise',
                'max_storage_size': 200 * 1024 * 1024 * 1024,  # 200GB
                'price': 50,
                'billing_period': 'monthly',
                'features': [
                    '200GB Storage',
                    'Advanced File Sharing',
                    '24/7 Priority Support',
                    '2GB File Size Limit',
                    'No Ads',
                    'Advanced Analytics',
                    'Custom Branding',
                    'Team Collaboration',
                    'API Access'
                ],
                'display_order': 3
            }
        ]
        
        for plan_data in plans_data:
            if plan_data['price'] > 0:
                # Create product in Stripe
                try:
                    product = stripe.Product.create(
                        name=plan_data['name'],
                        description=f"{plan_data['max_storage_size'] // (1024*1024*1024)}GB Cloud Storage Plan"
                    )
                    
                    # Create price in Stripe
                    price = stripe.Price.create(
                        product=product.id,
                        unit_amount=int(plan_data['price'] * 100),  # Convert to cents
                        currency='usd',
                        recurring={'interval': 'month'},
                    )
                    
                    plan_data['stripe_price_id'] = price.id
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error creating Stripe product for {plan_data["name"]}: {str(e)}')
                    )
                    continue
            
            # Create or update plan in database
            plan, created = StoragePlan.objects.update_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created plan: {plan.name}')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Updated plan: {plan.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully setup all payment plans!')
        )