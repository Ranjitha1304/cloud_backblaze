import boto3
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from .models import UserProfile, StoragePlan
import logging

# Set up logger
logger = logging.getLogger(__name__)

def check_storage_usage():
    """Check current storage usage to avoid surprise costs"""
    try:
        client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        # Calculate total storage used
        paginator = client.get_paginator('list_objects_v2')
        total_size = 0
        file_count = 0
        
        for page in paginator.paginate(Bucket=settings.AWS_STORAGE_BUCKET_NAME):
            if 'Contents' in page:
                for obj in page['Contents']:
                    total_size += obj['Size']
                    file_count += 1
        
        result = {
            'total_size_gb': total_size / (1024 ** 3),
            'file_count': file_count,
            'free_tier_remaining': max(0, 10 - (total_size / (1024 ** 3)))  # 10GB free
        }
        
        logger.info(f"Storage usage checked: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error checking storage usage: {e}")
        return {
            'total_size_gb': 0,
            'file_count': 0,
            'free_tier_remaining': 10
        }

def send_welcome_email(user):
    """Send welcome email to new user"""
    try:
        logger.info(f"Attempting to send welcome email to user: {user.username}, email: {user.email}")
        
        # Check if user has email
        if not user.email:
            logger.error(f"Cannot send welcome email: User {user.username} has no email address")
            return False
        
        user_profile = UserProfile.objects.get(user=user)
        context = {
            'user': user,
            'user_profile': user_profile,
            'plan': user_profile.storage_plan,
            'storage_limit': user_profile.storage_plan.max_storage_size,
            'storage_limit_gb': user_profile.storage_plan.max_storage_size / (1024**3),
        }
        
        logger.info(f"Rendering welcome email template for {user.username}")
        html_message = render_to_string('emails/welcome_email.html', context)
        plain_message = strip_tags(html_message)
        
        logger.info(f"Sending welcome email to {user.email}")
        result = send_mail(
            subject=settings.EMAIL_TEMPLATES['WELCOME']['subject'],
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        if result == 1:
            logger.info(f"Welcome email successfully sent to {user.email}")
            return True
        else:
            logger.error(f"Failed to send welcome email to {user.email}. Send mail returned: {result}")
            return False
            
    except UserProfile.DoesNotExist:
        logger.error(f"Cannot send welcome email: UserProfile does not exist for user {user.username}")
        return False
    except Exception as e:
        logger.error(f"Error sending welcome email to {user.email}: {str(e)}")
        return False

def send_subscription_email(user, old_plan, new_plan, action='upgrade'):
    """Send subscription change email"""
    try:
        logger.info(f"Attempting to send {action} email to user: {user.username}")
        logger.info(f"Plan change: {old_plan.name} (₹{old_plan.price}) -> {new_plan.name} (₹{new_plan.price})")
        
        # Check if user has email
        if not user.email:
            logger.error(f"Cannot send subscription email: User {user.username} has no email address")
            return False
        
        user_profile = UserProfile.objects.get(user=user)
        context = {
            'user': user,
            'user_profile': user_profile,
            'old_plan': old_plan,
            'new_plan': new_plan,
            'action': action,
            'new_storage_limit': new_plan.max_storage_size,
            'new_storage_limit_gb': new_plan.max_storage_size / (1024**3),
        }
        
        # Determine subject and template based on action
        if action == 'upgrade':
            subject = settings.EMAIL_TEMPLATES['SUBSCRIPTION_UPGRADE']['subject']
            template = 'emails/subscription_upgrade.html'
        elif action == 'downgrade':
            subject = settings.EMAIL_TEMPLATES['SUBSCRIPTION_DOWNGRADE']['subject']
            template = 'emails/subscription_change.html'
        else:  # change
            subject = 'Subscription Updated - Cloud Storage'
            template = 'emails/subscription_change.html'
        
        logger.info(f"Using template: {template}, subject: {subject}")
        
        # Check if template exists
        try:
            html_message = render_to_string(template, context)
        except Exception as template_error:
            logger.error(f"Template error: {template_error}. Using fallback template.")
            # Fallback to simple text email
            plain_message = f"""
            Hello {user.username},
            
            Your Cloud Storage subscription has been changed.
            
            Old Plan: {old_plan.name}
            New Plan: {new_plan.name}
            Storage: {new_plan.max_storage_size / (1024**3):.1f} GB
            Price: ₹{new_plan.price}/{new_plan.billing_period}
            
            Thank you,
            Cloud Storage Team
            """
            
            result = send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        else:
            plain_message = strip_tags(html_message)
            
            logger.info(f"Sending {action} email to {user.email}")
            result = send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
        
        if result == 1:
            logger.info(f"Subscription {action} email successfully sent to {user.email}")
            return True
        else:
            logger.error(f"Failed to send subscription email to {user.email}. Send mail returned: {result}")
            return False
            
    except UserProfile.DoesNotExist:
        logger.error(f"Cannot send subscription email: UserProfile does not exist for user {user.username}")
        return False
    except Exception as e:
        logger.error(f"Error sending subscription email to {user.email}: {str(e)}")
        return False

def send_payment_success_email(user, plan, amount):
    """Send payment success email"""
    try:
        logger.info(f"Attempting to send payment success email to user: {user.username}")
        
        # Check if user has email
        if not user.email:
            logger.error(f"Cannot send payment success email: User {user.username} has no email address")
            return False
        
        context = {
            'user': user,
            'plan': plan,
            'amount': amount,
        }
        
        logger.info(f"Rendering payment success email template for {user.username}")
        html_message = render_to_string('emails/payment_success.html', context)
        plain_message = strip_tags(html_message)
        
        logger.info(f"Sending payment success email to {user.email}")
        result = send_mail(
            subject='Payment Successful - Cloud Storage',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        if result == 1:
            logger.info(f"Payment success email successfully sent to {user.email}")
            return True
        else:
            logger.error(f"Failed to send payment success email to {user.email}. Send mail returned: {result}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending payment success email to {user.email}: {str(e)}")
        return False

def debug_email_settings():
    """Debug function to check email configuration"""
    debug_info = {
        'EMAIL_BACKEND': getattr(settings, 'EMAIL_BACKEND', 'Not set'),
        'EMAIL_HOST': getattr(settings, 'EMAIL_HOST', 'Not set'),
        'EMAIL_PORT': getattr(settings, 'EMAIL_PORT', 'Not set'),
        'EMAIL_USE_TLS': getattr(settings, 'EMAIL_USE_TLS', 'Not set'),
        'EMAIL_HOST_USER': getattr(settings, 'EMAIL_HOST_USER', 'Not set'),
        'DEFAULT_FROM_EMAIL': getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not set'),
        'EMAIL_TEMPLATES': getattr(settings, 'EMAIL_TEMPLATES', {}),
    }
    
    logger.info("Email settings debug info:")
    for key, value in debug_info.items():
        logger.info(f"  {key}: {value}")
    
    return debug_info

def test_email_functionality(user):
    """Test email functionality for a user"""
    try:
        logger.info(f"Testing email functionality for user: {user.username}")
        
        # Debug email settings first
        debug_email_settings()
        
        # Test basic email
        test_result = send_mail(
            subject='Test Email - Cloud Storage',
            message='This is a test email from Cloud Storage.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        if test_result == 1:
            logger.info(f"Test email sent successfully to {user.email}")
            return True
        else:
            logger.error(f"Test email failed. Send mail returned: {test_result}")
            return False
            
    except Exception as e:
        logger.error(f"Test email functionality failed: {str(e)}")
        return False