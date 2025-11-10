from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Sum, Q 
from django.utils import timezone
import os
from .models import File, UserProfile, ShareLink, StoragePlan, Folder, Subscription, Trash
from .forms import CustomUserCreationForm, FileUploadForm, FileShareForm, FolderCreateForm, MoveFileForm

from django.urls import reverse  
from datetime import datetime  
import stripe  
from django.conf import settings
import json

from .utils import send_welcome_email, send_subscription_email, send_payment_success_email

from django.db import models

from .models import Task
from .forms import TaskCreateForm, TaskEditForm

from django.utils import timezone

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile with free plan
            free_plan = StoragePlan.objects.get_or_create(
                name="Free",
                defaults={'max_storage_size': 500 * 1024 * 1024, 'price': 0}
            )[0]
            UserProfile.objects.create(user=user, storage_plan=free_plan)
            
            # Send welcome email
            try:
                send_welcome_email(user)
            except Exception as e:
                print(f"Failed to send welcome email: {e}")
                # Continue with registration even if email fails
            
            login(request, user)
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    """Dashboard view - Fixed to handle missing UserProfiles"""
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        # Create UserProfile if it doesn't exist
        free_plan = StoragePlan.objects.get_or_create(
            name="Free",
            defaults={'max_storage_size': 500 * 1024 * 1024, 'price': 0}
        )[0]
        user_profile = UserProfile.objects.create(
            user=request.user,
            storage_plan=free_plan,
            used_storage=0
        )
    
    files = File.objects.filter(owner=request.user, is_deleted=False).order_by('-uploaded_at')
    total_files = files.count()
    
    # Calculate storage usage
    total_size = files.aggregate(Sum('size'))['size__sum'] or 0
    user_profile.used_storage = total_size
    user_profile.save()
    
    # Get view preference from session or default to 'grid'
    view_mode = request.session.get('dashboard_view_mode', 'grid')
    
    context = {
        'user_profile': user_profile,
        'files': files[:8],  # Show 8 recent files
        'total_files': total_files,
        'total_size': total_size,
        'storage_usage_percent': user_profile.get_storage_usage_percent(),
        'view_mode': view_mode,  # Add view mode to context
    }
    return render(request, 'dashboard.html', context)

@login_required
def toggle_dashboard_view(request):
    """Toggle between grid and list view for dashboard"""
    if request.method == 'POST':
        current_view = request.session.get('dashboard_view_mode', 'grid')
        new_view = 'list' if current_view == 'grid' else 'grid'
        request.session['dashboard_view_mode'] = new_view
        return JsonResponse({'success': True, 'view_mode': new_view})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.owner = request.user
            file_obj.size = file_obj.file.size
            file_obj.name = file_obj.file.name
            file_obj.file_type = os.path.splitext(file_obj.file.name)[1].lower()
            
            # Check storage limit
            user_profile = UserProfile.objects.get(user=request.user)
            if user_profile.used_storage + file_obj.size > user_profile.storage_plan.max_storage_size:
                return JsonResponse({
                    'success': False,
                    'error': 'Storage limit exceeded'
                })
            
            file_obj.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid file'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def delete_file(request, file_id):
    """Move file to trash instead of permanent deletion"""
    if request.method == 'POST':
        try:
            file_obj = get_object_or_404(File, id=file_id, owner=request.user)
            
            # Create trash record
            Trash.objects.create(
                user=request.user,
                file=file_obj,
                original_folder=file_obj.folder,
                scheduled_permanent_deletion=timezone.now() + timezone.timedelta(days=30)
            )
            
            # Mark file as deleted
            file_obj.is_deleted = True
            file_obj.save()
            
            return JsonResponse({
                'success': True,
                'message': 'File moved to trash'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def download_file(request, file_id):
    """Generate a fresh signed URL for downloading a file"""
    try:
        file_obj = get_object_or_404(File, id=file_id, owner=request.user)
        
        # Generate a fresh signed URL
        from django.conf import settings
        import boto3
        from botocore.client import Config
        
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )
        
        # Find the correct file key in Backblaze
        file_key = file_obj.file.name
        possible_keys = [
            file_key,  # Original key from database
            f"media/{file_key}",  # With media/ prefix
        ]
        
        actual_key = file_key
        for test_key in possible_keys:
            try:
                s3_client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=test_key)
                actual_key = test_key
                break
            except:
                continue
        
        # Generate presigned URL valid for 1 hour that forces download
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': actual_key,
                'ResponseContentDisposition': f'attachment; filename="{file_obj.name}"'  # This forces download
            },
            ExpiresIn=3600  # 1 hour in seconds
        )
        
        # Redirect to the fresh signed URL
        return redirect(presigned_url)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def create_share_link(request, file_id):
    """Create a shareable link for a file - POST only"""
    if request.method == 'POST':
        try:
            file_obj = get_object_or_404(File, id=file_id, owner=request.user)
            
            # Create share link
            share_link = ShareLink.objects.create(file=file_obj)
            
            # Handle expiration if provided
            expires_in = request.POST.get('expires_in')
            if expires_in and expires_in.isdigit():
                share_link.expires_at = timezone.now() + timezone.timedelta(days=int(expires_in))
                share_link.save()
            
            # Build the share URL
            share_url = request.build_absolute_uri(f'/share/{share_link.token}/')
            
            return JsonResponse({
                'success': True, 
                'share_url': share_url,
                'expires_at': share_link.expires_at.isoformat() if share_link.expires_at else None
            })
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def share_file(request, token):
    """View to handle shared file access - GET only"""
    try:
        # Get the share link
        share_link = get_object_or_404(ShareLink, token=token, is_active=True)
        
        # Check if link has expired
        if share_link.expires_at and share_link.expires_at < timezone.now():
            return render(request, 'share_expired.html', {
                'error': 'This share link has expired'
            })
        
        file_obj = share_link.file
        
        # Generate a fresh signed URL that's valid for a short time
        from django.conf import settings
        import boto3
        from botocore.client import Config
        
        # Create a presigned URL that's valid for 1 hour
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )
        
        # Find the correct file key in Backblaze
        file_key = file_obj.file.name
        possible_keys = [
            file_key,  # Original key from database
            f"media/{file_key}",  # With media/ prefix
        ]
        
        actual_key = file_key
        for test_key in possible_keys:
            try:
                s3_client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=test_key)
                actual_key = test_key
                break
            except:
                continue
        
        # Generate presigned URL valid for 1 hour that forces download
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': actual_key,
                'ResponseContentDisposition': f'attachment; filename="{file_obj.name}"'  # This forces download
            },
            ExpiresIn=3600  # 1 hour in seconds
        )
        
        # Render the share page with the fresh presigned URL
        return render(request, 'share_file.html', {
            'file': file_obj,
            'share_link': share_link,
            'download_url': presigned_url
        })
        
    except Http404:
        return render(request, 'share_error.html', {
            'error': 'Share link not found or inactive'
        })
    except Exception as e:
        return render(request, 'share_error.html', {
            'error': f'Error accessing file: {str(e)}'
        })

@login_required
def file_list(request, folder_id=None):
    """File list with folder support and enhanced filtering"""
    current_folder = None
    if folder_id:
        current_folder = get_object_or_404(Folder, id=folder_id, owner=request.user)
    
    # Get base queryset
    files = File.objects.filter(owner=request.user, folder=current_folder, is_deleted=False)
    
    # Apply file type filter
    file_type_filter = request.GET.get('file_type', '')
    if file_type_filter:
        files = filter_files_by_type(files, file_type_filter)
    
    # Apply date filter
    date_filter = request.GET.get('date_filter', '')
    if date_filter:
        files = filter_files_by_date(files, date_filter)
    
    # Apply starred filter
    starred_filter = request.GET.get('starred', '')
    if starred_filter == 'true':
        files = files.filter(is_starred=True)
    
    # Order files
    files = files.order_by('-uploaded_at')
    
    # Get folders in current folder
    folders = Folder.objects.filter(owner=request.user, parent_folder=current_folder).order_by('name')
    
    # Get all folders for move dropdown
    all_folders = Folder.objects.filter(owner=request.user).exclude(id=current_folder.id if current_folder else None)
    
    # Folder creation form
    folder_form = FolderCreateForm()
    
    # Get filter counts for UI
    filter_counts = get_filter_counts(File.objects.filter(owner=request.user, folder=current_folder))
    
    context = {
        'files': files,
        'folders': folders,
        'current_folder': current_folder,
        'all_folders': all_folders,
        'folder_form': folder_form,
        'file_type_filter': file_type_filter,
        'date_filter': date_filter,
        'starred_filter': starred_filter == 'true',
        'filter_counts': filter_counts,
    }
    return render(request, 'file_list.html', context)

def filter_files_by_type(files_queryset, file_type):
    """Filter files by file type category"""
    file_type_groups = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'],
        'document': ['.doc', '.docx', '.txt', '.rtf', '.odt'],
        'pdf': ['.pdf'],
        'spreadsheet': ['.xls', '.xlsx', '.csv', '.ods'],
        'presentation': ['.ppt', '.pptx', '.odp'],
        'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'],
        'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
        'archive': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'code': ['.html', '.css', '.js', '.py', '.java', '.cpp', '.c', '.php', '.xml', '.json'],
    }
    
    if file_type in file_type_groups:
        extensions = file_type_groups[file_type]
        query = models.Q()
        for ext in extensions:
            query |= models.Q(file_type__iexact=ext)
        return files_queryset.filter(query)
    
    # If specific extension is provided
    elif file_type.startswith('.'):
        return files_queryset.filter(file_type__iexact=file_type)
    
    return files_queryset

def filter_files_by_date(files_queryset, date_filter):
    """Filter files by date range"""
    from django.utils import timezone
    from datetime import timedelta
    
    now = timezone.now()
    
    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return files_queryset.filter(uploaded_at__gte=start_date)
    
    elif date_filter == 'week':
        start_date = now - timedelta(days=7)
        return files_queryset.filter(uploaded_at__gte=start_date)
    
    elif date_filter == 'month':
        start_date = now - timedelta(days=30)
        return files_queryset.filter(uploaded_at__gte=start_date)
    
    elif date_filter == 'year':
        start_date = now - timedelta(days=365)
        return files_queryset.filter(uploaded_at__gte=start_date)
    
    return files_queryset

def get_filter_counts(files_queryset):
    """Get counts for each filter category"""
    from django.db.models import Count
    from django.utils import timezone
    from datetime import timedelta
    
    now = timezone.now()
    
    # Date filter counts
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    year_start = now - timedelta(days=365)
    
    date_counts = {
        'today': files_queryset.filter(uploaded_at__gte=today_start).count(),
        'week': files_queryset.filter(uploaded_at__gte=week_start).count(),
        'month': files_queryset.filter(uploaded_at__gte=month_start).count(),
        'year': files_queryset.filter(uploaded_at__gte=year_start).count(),
        'all': files_queryset.count(),
    }
    
    # File type counts
    file_type_groups = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'],
        'document': ['.doc', '.docx', '.txt', '.rtf', '.odt'],
        'pdf': ['.pdf'],
        'spreadsheet': ['.xls', '.xlsx', '.csv', '.ods'],
        'presentation': ['.ppt', '.pptx', '.odp'],
        'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'],
        'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
        'archive': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'code': ['.html', '.css', '.js', '.py', '.java', '.cpp', '.c', '.php', '.xml', '.json'],
    }
    
    file_type_counts = {}
    for file_type, extensions in file_type_groups.items():
        query = models.Q()
        for ext in extensions:
            query |= models.Q(file_type__iexact=ext)
        file_type_counts[file_type] = files_queryset.filter(query).count()
    
    # Count for "other" file types
    all_extensions = []
    for extensions in file_type_groups.values():
        all_extensions.extend(extensions)
    
    file_type_counts['other'] = files_queryset.exclude(
        file_type__in=all_extensions
    ).count()
    
    # Starred count
    starred_count = files_queryset.filter(is_starred=True).count()
    
    return {
        'date': date_counts,
        'file_type': file_type_counts,
        'starred': starred_count,  # Add starred count
    }

@login_required
def create_folder(request):
    """Create a new folder"""
    if request.method == 'POST':
        form = FolderCreateForm(request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.owner = request.user
            folder.save()
            return JsonResponse({'success': True, 'folder_id': folder.id, 'folder_name': folder.name})
        else:
            return JsonResponse({'success': False, 'error': form.errors})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def move_file(request, file_id):
    """Move file to a folder"""
    if request.method == 'POST':
        file_obj = get_object_or_404(File, id=file_id, owner=request.user)
        form = MoveFileForm(request.user, request.POST)
        
        if form.is_valid():
            folder = form.cleaned_data['folder']
            file_obj.folder = folder
            file_obj.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': form.errors})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def delete_folder(request, folder_id):
    """Delete a folder (must be empty)"""
    if request.method == 'POST':
        folder = get_object_or_404(Folder, id=folder_id, owner=request.user)
        
        # Check if folder is empty
        if folder.files.exists() or folder.subfolders.exists():
            return JsonResponse({
                'success': False, 
                'error': 'Folder is not empty. Please delete all files and subfolders first.'
            })
        
        folder.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# NEW FUNCTIONALITY FOR PUBLIC FILES
@login_required
def toggle_file_visibility(request, file_id):
    """Toggle file between public and private"""
    if request.method == 'POST':
        try:
            file_obj = get_object_or_404(File, id=file_id, owner=request.user)
            file_obj.is_public = not file_obj.is_public
            file_obj.save()
            
            return JsonResponse({
                'success': True, 
                'is_public': file_obj.is_public,
                'message': f'File is now {"public" if file_obj.is_public else "private"}'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def public_file_access(request, file_id):
    """Direct access to public files without authentication"""
    try:
        file_obj = get_object_or_404(File, id=file_id, is_public=True)
        
        # Generate a fresh signed URL for public access
        from django.conf import settings
        import boto3
        from botocore.client import Config
        
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )
        
        # Find the correct file key
        file_key = file_obj.file.name
        possible_keys = [
            file_key,
            f"media/{file_key}",
        ]
        
        actual_key = file_key
        for test_key in possible_keys:
            try:
                s3_client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=test_key)
                actual_key = test_key
                break
            except:
                continue
        
        # Generate presigned URL valid for 1 hour
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': actual_key,
                'ResponseContentDisposition': f'attachment; filename="{file_obj.name}"'
            },
            ExpiresIn=3600
        )
        
        # Get public URL for sharing
        public_url = request.build_absolute_uri(f'/public/file/{file_obj.id}/')
        
        # Render a simple public file page
        return render(request, 'public_file.html', {
            'file': file_obj,
            'download_url': presigned_url,
            'public_url': public_url
        })
        
    except Http404:
        return render(request, 'public_file_error.html', {
            'error': 'File not found or not publicly accessible'
        })
    except Exception as e:
        return render(request, 'public_file_error.html', {
            'error': f'Error accessing file: {str(e)}'
        })
    

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def pricing_plans(request):
    """Display all available pricing plans"""
    plans = StoragePlan.objects.filter(is_active=True).order_by('price')
    user_profile = UserProfile.objects.get(user=request.user)
    
    context = {
        'plans': plans,
        'current_plan': user_profile.storage_plan,
        'user_profile': user_profile,
    }
    return render(request, 'pricing.html', context)

@login_required
def create_checkout_session(request, plan_id):
    """Create Stripe checkout session - Fixed version"""
    try:
        print(f"=== CHECKOUT SESSION DEBUG ===")
        print(f"Creating checkout session for plan ID: {plan_id}")
        print(f"User: {request.user.username}, Email: {request.user.email}")
        
        # Simple approach - just get the plan by ID
        plan = get_object_or_404(StoragePlan, id=plan_id, is_active=True)
        user_profile = UserProfile.objects.get(user=request.user)
        
        print(f"Plan found: {plan.name}, Price: Rs.{plan.price}")
        print(f"Current user plan: {user_profile.storage_plan.name}, Price: Rs.{user_profile.storage_plan.price}")
        
        # Check if it's a free plan
        if plan.price == 0:
            print("🆓 Handling FREE plan selection")
            # Store old plan for email
            old_plan = user_profile.storage_plan

            print(f"Free plan selection - Old: {old_plan.name}, New: {plan.name}")
            print(f"Should send downgrade email: {old_plan.price > plan.price}")

            # Handle free plan selection
            user_profile.storage_plan = plan
            user_profile.save()
            print("✅ Free plan updated in database")

            # Send subscription change email for downgrade
            try:
                if old_plan.price > plan.price:  # Only send for downgrades to free
                    print("📧 Sending downgrade email for free plan selection")
                    email_sent = send_subscription_email(request.user, old_plan, plan, 'downgrade')
                    print(f"Downgrade email sent: {email_sent}")
                else:
                    print("ℹ️ No downgrade email sent - not a downgrade scenario")
            except Exception as e:
                print(f"❌ Failed to send subscription email: {e}")
                import traceback
                print(f"Free plan email error: {traceback.format_exc()}")

            print("🔄 Redirecting to dashboard after free plan selection")
            return JsonResponse({
                'success': True,
                'message': f'Switched to {plan.name} plan successfully',
                'redirect_url': '/dashboard/'  # Changed to dashboard for free plans
            })
        
        # For paid plans, check if Stripe price ID exists
        if not plan.stripe_price_id:
            print("❌ No Stripe price ID found")
            return JsonResponse({
                'error': 'This plan is not configured for payments. Please contact support.'
            }, status=400)
        
        print(f"💰 Processing PAID plan: {plan.name}")
        print(f"Stripe price ID: {plan.stripe_price_id}")
        
        # Create or get Stripe customer for paid plans
        if not user_profile.stripe_customer_id:
            print("👤 Creating new Stripe customer")
            customer = stripe.Customer.create(
                email=request.user.email,
                name=request.user.username,
                metadata={'user_id': request.user.id}
            )
            user_profile.stripe_customer_id = customer.id
            user_profile.save()
            print(f"✅ Stripe customer created: {user_profile.stripe_customer_id}")
        
        # Create checkout session with direct URLs
        print("🛒 Creating Stripe checkout session")
        success_url = request.build_absolute_uri('/payment/success/') + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = request.build_absolute_uri('/payment/cancel/')
        
        print(f"Success URL: {success_url}")
        print(f"Cancel URL: {cancel_url}")
        
        checkout_session = stripe.checkout.Session.create(
            customer=user_profile.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': plan.stripe_price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'plan_id': str(plan.id),
                'user_id': str(request.user.id)
            }
        )
        
        print(f"✅ Checkout session created: {checkout_session.url}")
        print(f"🔗 Checkout URL: {checkout_session.url}")
        return JsonResponse({'checkout_url': checkout_session.url})
        
    except Exception as e:
        print(f"❌ Checkout session error: {e}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=400)
                    

@login_required
def payment_success(request):
    """Handle successful payment - Check status immediately"""
    session_id = request.GET.get('session_id')
    
    # Add debug logging at the start of payment_success
    print(f"=== PAYMENT SUCCESS DEBUG ===")
    print(f"User: {request.user.username}")
    print(f"User email: {request.user.email}")
    print(f"Session ID: {session_id}")
    
    if session_id:
        try:
            # Retrieve the session from Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check if payment was successful
            if session.payment_status == 'paid':
                plan_id = session.metadata.get('plan_id')
                user_id = session.metadata.get('user_id')
                
                print(f"Plan ID: {plan_id}")
                print(f"User ID from session: {user_id}, Current user ID: {request.user.id}")
                
                if str(request.user.id) == user_id:
                    plan = StoragePlan.objects.get(id=plan_id)
                    user_profile = UserProfile.objects.get(user=request.user)
                    
                    # Store old plan for email
                    old_plan = user_profile.storage_plan
                    
                    print(f"=== PLAN COMPARISON DEBUG ===")
                    print(f"Old plan: {old_plan.name} (ID: {old_plan.id}, Price: {old_plan.price})")
                    print(f"New plan: {plan.name} (ID: {plan.id}, Price: {plan.price})")
                    print(f"Plan IDs different: {old_plan.id != plan.id}")
                    print(f"Old price type: {type(old_plan.price)}, Value: {old_plan.price}")
                    print(f"New price type: {type(plan.price)}, Value: {plan.price}")
                    
                    # Convert to float for safe comparison
                    old_price = float(old_plan.price) if old_plan.price else 0.0
                    new_price = float(plan.price) if plan.price else 0.0
                    
                    print(f"Float comparison - Old: {old_price}, New: {new_price}")
                    print(f"Upgrade condition (old < new): {old_price < new_price}")
                    print(f"Downgrade condition (old > new): {old_price > new_price}")
                    print(f"Same price condition (old == new): {old_price == new_price}")
                    
                    # Update user's plan immediately
                    user_profile.storage_plan = plan
                    user_profile.save()
                    print("User plan updated in database")
                    
                    # Get subscription details
                    subscription = stripe.Subscription.retrieve(session.subscription)
                    
                    # Create subscription record
                    Subscription.objects.update_or_create(
                        stripe_subscription_id=subscription.id,
                        defaults={
                            'user': request.user,
                            'plan': plan,
                            'status': subscription.status,
                            'current_period_start': datetime.fromtimestamp(subscription.current_period_start),
                            'current_period_end': datetime.fromtimestamp(subscription.current_period_end),
                            'cancel_at_period_end': subscription.cancel_at_period_end,
                        }
                    )
                    print("Subscription record created/updated")
                    
                    # Send subscription upgrade email - FIXED LOGIC
                    print(f"=== EMAIL SENDING DEBUG ===")
                    try:
                        # Always send email if plan actually changed
                        if old_plan.id != plan.id:
                            print(f"Plans are different - proceeding with email sending")
                            
                            if old_price < new_price:
                                print("🔺 SENDING UPGRADE EMAIL")
                                email_sent = send_subscription_email(request.user, old_plan, plan, 'upgrade')
                                print(f"Upgrade email sent: {email_sent}")
                            elif old_price > new_price:
                                print("🔻 SENDING DOWNGRADE EMAIL")
                                email_sent = send_subscription_email(request.user, old_plan, plan, 'downgrade')
                                print(f"Downgrade email sent: {email_sent}")
                            else:
                                print("🔄 SENDING CHANGE EMAIL (same price)")
                                email_sent = send_subscription_email(request.user, old_plan, plan, 'change')
                                print(f"Change email sent: {email_sent}")
                            
                            print("💰 SENDING PAYMENT SUCCESS EMAIL")
                            payment_email_sent = send_payment_success_email(request.user, plan, plan.price)
                            print(f"Payment success email sent: {payment_email_sent}")
                            
                        else:
                            print("❌ No email sent - Plan ID is the same (no change)")
                            
                    except Exception as e:
                        print(f"❌ ERROR sending subscription email: {e}")
                        import traceback
                        print(f"Email error traceback: {traceback.format_exc()}")
                    
                    return render(request, 'payment_success.html', {
                        'plan': plan,
                        'subscription_id': subscription.id
                    })
                else:
                    print(f"❌ User ID mismatch! Session user: {user_id}, Current user: {request.user.id}")
            else:
                print(f"❌ Payment not completed yet. Status: {session.payment_status}")
                # Payment not completed yet
                return render(request, 'payment_processing.html', {
                    'session_id': session_id
                })
                
        except Exception as e:
            print(f"❌ Payment success error: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
    
    else:
        print("❌ No session ID provided in request")
    
    # If anything fails, show generic success page
    return render(request, 'payment_success.html')


@login_required
def check_payment_status(request):
    """AJAX endpoint to check payment status"""
    session_id = request.GET.get('session_id')
    
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            
            if session.payment_status == 'paid':
                # Payment successful - update user's plan
                plan_id = session.metadata.get('plan_id')
                user_id = session.metadata.get('user_id')
                
                if str(request.user.id) == user_id:
                    plan = StoragePlan.objects.get(id=plan_id)
                    user_profile = UserProfile.objects.get(user=request.user)
                    user_profile.storage_plan = plan
                    user_profile.save()
                    
                    return JsonResponse({
                        'status': 'success',
                        'plan_name': plan.name
                    })
            else:
                return JsonResponse({
                    'status': 'processing',
                    'message': 'Payment still processing...'
                })
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid session'
    })


@login_required
def payment_cancel(request):
    """Handle canceled payment"""
    return render(request, 'payment_cancel.html')

@login_required
def subscription_management(request):
    """Manage user's subscription"""
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        subscription = Subscription.objects.filter(user=request.user, status='active').first()
        
        if subscription and user_profile.stripe_customer_id:
            # Retrieve subscription details from Stripe
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            upcoming_invoice = stripe.Invoice.upcoming(customer=user_profile.stripe_customer_id)
            
            context = {
                'subscription': subscription,
                'stripe_subscription': stripe_subscription,
                'upcoming_invoice': upcoming_invoice,
                'user_profile': user_profile,
            }
            return render(request, 'subscription_management.html', context)
    
    except Exception as e:
        print(f"Subscription management error: {e}")
    
    return redirect('pricing_plans')

@login_required
def cancel_subscription(request):
    """Cancel user's subscription"""
    if request.method == 'POST':
        try:
            subscription = Subscription.objects.get(user=request.user, status='active')
            
            # Cancel at period end
            canceled_subscription = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            subscription.cancel_at_period_end = True
            subscription.save()
            
            return JsonResponse({'success': True, 'message': 'Subscription will cancel at period end'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhooks"""
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)
    
    # Handle different webhook events
    if event['type'] == 'customer.subscription.updated':
        handle_subscription_updated(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        handle_subscription_deleted(event['data']['object'])
    
    return HttpResponse(status=200)

def handle_subscription_updated(subscription):
    """Handle subscription updated webhook"""
    try:
        sub = Subscription.objects.get(stripe_subscription_id=subscription['id'])
        sub.status = subscription['status']
        sub.current_period_start = datetime.fromtimestamp(subscription['current_period_start'])
        sub.current_period_end = datetime.fromtimestamp(subscription['current_period_end'])
        sub.cancel_at_period_end = subscription['cancel_at_period_end']
        sub.save()
        
        # If subscription is canceled and period ended, downgrade to free plan
        if (subscription['status'] in ['canceled', 'unpaid'] and 
            datetime.fromtimestamp(subscription['current_period_end']) < timezone.now()):
            free_plan = StoragePlan.objects.get(plan_type='free')
            user_profile = UserProfile.objects.get(user=sub.user)
            user_profile.storage_plan = free_plan
            user_profile.save()
            
    except Subscription.DoesNotExist:
        pass

def handle_subscription_deleted(subscription):
    """Handle subscription deleted webhook"""
    try:
        sub = Subscription.objects.get(stripe_subscription_id=subscription['id'])
        sub.status = 'canceled'
        sub.save()
        
        # Downgrade to free plan
        free_plan = StoragePlan.objects.get(plan_type='free')
        user_profile = UserProfile.objects.get(user=sub.user)
        user_profile.storage_plan = free_plan
        user_profile.save()
        
    except Subscription.DoesNotExist:
        pass

# Update your existing upload_file view to use the new storage check
@login_required
def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.owner = request.user
            file_obj.size = file_obj.file.size
            file_obj.name = file_obj.file.name
            file_obj.file_type = os.path.splitext(file_obj.file.name)[1].lower()
            
            # Check storage limit using new method
            user_profile = UserProfile.objects.get(user=request.user)
            if not user_profile.can_upload_file(file_obj.size):
                return JsonResponse({
                    'success': False,
                    'error': f'Storage limit exceeded. Upgrade your plan to upload more files.'
                })
            
            file_obj.save()
            
            # Update used storage
            user_profile.used_storage += file_obj.size
            user_profile.save()
            
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid file'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def debug_plans(request):
    """Debug view to see available plans"""
    plans = StoragePlan.objects.all()
    plan_data = []
    for plan in plans:
        plan_data.append({
            'id': str(plan.id),  # Convert to string for JSON
            'name': plan.name,
            'price': float(plan.price),  # Convert to float for JSON
            'stripe_price_id': plan.stripe_price_id,
            'is_active': plan.is_active,
            'max_storage': plan.max_storage_size,
            'plan_type': plan.plan_type
        })
    
    return JsonResponse({'plans': plan_data})


@login_required
def test_subscription_email(request):
    """Test endpoint to manually trigger subscription emails"""
    try:
        user = request.user
        user_profile = UserProfile.objects.get(user=user)
        
        # Get two different plans for testing
        free_plan = StoragePlan.objects.filter(plan_type='free').first()
        paid_plan = StoragePlan.objects.filter(plan_type='basic').first() or StoragePlan.objects.filter(plan_type='pro').first()
        
        if not free_plan or not paid_plan:
            return JsonResponse({'error': 'Need at least two different plans for testing'})
        
        print(f"=== MANUAL EMAIL TEST ===")
        print(f"Testing with user: {user.username} ({user.email})")
        print(f"Current plan: {user_profile.storage_plan.name}")
        print(f"Test plans - Free: {free_plan.name}, Paid: {paid_plan.name}")
        
        # Test upgrade email
        print("Testing UPGRADE email...")
        upgrade_result = send_subscription_email(user, free_plan, paid_plan, 'upgrade')
        print(f"Upgrade email result: {upgrade_result}")
        
        # Test downgrade email  
        print("Testing DOWNGRADE email...")
        downgrade_result = send_subscription_email(user, paid_plan, free_plan, 'downgrade')
        print(f"Downgrade email result: {downgrade_result}")
        
        # Test payment success email
        print("Testing PAYMENT SUCCESS email...")
        payment_result = send_payment_success_email(user, paid_plan, paid_plan.price)
        print(f"Payment success email result: {payment_result}")
        
        return JsonResponse({
            'success': True,
            'upgrade_email_sent': upgrade_result,
            'downgrade_email_sent': downgrade_result,
            'payment_email_sent': payment_result,
            'message': 'Check server console for detailed logs'
        })
        
    except Exception as e:
        print(f"Test email error: {e}")
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)})
    

@login_required
def debug_payment_flow(request):
    """Debug view to test the payment flow"""
    print("=== PAYMENT FLOW DEBUG ===")
    print(f"User: {request.user.username}")
    print(f"User email: {request.user.email}")
    
    # Test email functionality
    from .utils import test_email_functionality, debug_email_settings
    debug_email_settings()
    test_result = test_email_functionality(request.user)
    
    # Test subscription email directly
    from .utils import send_subscription_email, send_payment_success_email
    from .models import StoragePlan
    
    free_plan = StoragePlan.objects.filter(plan_type='free').first()
    paid_plan = StoragePlan.objects.exclude(plan_type='free').first()
    
    if free_plan and paid_plan:
        print("Testing subscription emails...")
        upgrade_result = send_subscription_email(request.user, free_plan, paid_plan, 'upgrade')
        downgrade_result = send_subscription_email(request.user, paid_plan, free_plan, 'downgrade')
        payment_result = send_payment_success_email(request.user, paid_plan, paid_plan.price)
        
        print(f"Upgrade email: {upgrade_result}")
        print(f"Downgrade email: {downgrade_result}")
        print(f"Payment email: {payment_result}")
    
    return JsonResponse({
        'test_email_sent': test_result,
        'message': 'Check server console for debug information'
    })    



@login_required
def toggle_star_file(request, file_id):
    """Toggle star status for a file"""
    if request.method == 'POST':
        try:
            file_obj = get_object_or_404(File, id=file_id, owner=request.user)
            file_obj.is_starred = not file_obj.is_starred
            file_obj.save()
            
            return JsonResponse({
                'success': True, 
                'is_starred': file_obj.is_starred,
                'message': f'File {"starred" if file_obj.is_starred else "unstarred"} successfully'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def starred_files(request):
    """View to show only starred files"""
    files = File.objects.filter(owner=request.user, is_starred=True, is_deleted=False).order_by('-uploaded_at')
    folders = Folder.objects.filter(owner=request.user, parent_folder=None).order_by('name')
    
    # Get filter counts for UI
    filter_counts = get_filter_counts(File.objects.filter(owner=request.user))
    
    context = {
        'files': files,
        'folders': folders,
        'current_folder': None,
        'all_folders': Folder.objects.filter(owner=request.user),
        'folder_form': FolderCreateForm(),
        'file_type_filter': '',
        'date_filter': '',
        'starred_filter': True,  # Add this to indicate we're in starred view
        'filter_counts': filter_counts,
    }
    return render(request, 'file_list.html', context)


@login_required
def preview_file(request, file_id):
    """Preview file directly in browser"""
    try:
        file_obj = get_object_or_404(File, id=file_id, owner=request.user)
        
        # Generate a fresh signed URL for preview (inline display)
        import boto3
        from botocore.client import Config
        
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )
        
        # Find the correct file key
        file_key = file_obj.file.name
        possible_keys = [
            file_key,
            f"media/{file_key}",
        ]
        
        actual_key = file_key
        for test_key in possible_keys:
            try:
                s3_client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=test_key)
                actual_key = test_key
                break
            except:
                continue
        
        # Generate presigned URL for inline viewing (not download)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': actual_key,
                'ResponseContentDisposition': 'inline'  # This makes it open in browser
            },
            ExpiresIn=3600  # 1 hour
        )
        
        # Determine file category for appropriate preview
        file_type = file_obj.file_type.lower()
        
        # Files that can be previewed directly in browser
        previewable_types = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'],
            'pdf': ['.pdf'],
            'text': ['.txt', '.csv', '.log'],
            'code': ['.html', '.css', '.js', '.py', '.java', '.cpp', '.c', '.php', '.xml', '.json'],
        }
        
        file_category = 'other'
        for category, extensions in previewable_types.items():
            if file_type in extensions:
                file_category = category
                break
        
        context = {
            'file': file_obj,
            'preview_url': presigned_url,
            'file_category': file_category,
        }
        
        return render(request, 'file_preview.html', context)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

@login_required
def trash_view(request):
    """View to show all files in trash"""
    trash_items = Trash.objects.filter(user=request.user).select_related('file')
    files_in_trash = [item.file for item in trash_items]
    
    context = {
        'files': files_in_trash,
        'trash_count': len(files_in_trash),
        'is_trash_view': True,
    }
    return render(request, 'trash.html', context)

@login_required
def move_to_trash(request, file_id):
    """Move file to trash instead of permanent deletion"""
    if request.method == 'POST':
        try:
            file_obj = get_object_or_404(File, id=file_id, owner=request.user)
            
            # Create trash record
            Trash.objects.create(
                user=request.user,
                file=file_obj,
                original_folder=file_obj.folder,
                scheduled_permanent_deletion=timezone.now() + timezone.timedelta(days=30)  # 30 days retention
            )
            
            # Mark file as deleted
            file_obj.is_deleted = True
            file_obj.save()
            
            return JsonResponse({
                'success': True,
                'message': 'File moved to trash'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def restore_file(request, file_id):
    """Restore file from trash"""
    if request.method == 'POST':
        try:
            file_obj = get_object_or_404(File, id=file_id, owner=request.user, is_deleted=True)
            trash_item = get_object_or_404(Trash, file=file_obj, user=request.user)
            
            # Restore file
            file_obj.is_deleted = False
            file_obj.save()
            
            # Remove from trash
            trash_item.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'File restored successfully'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def restore_all_files(request):
    """Restore all files from trash"""
    if request.method == 'POST':
        try:
            trash_items = Trash.objects.filter(user=request.user)
            restored_count = 0
            
            for trash_item in trash_items:
                file_obj = trash_item.file
                file_obj.is_deleted = False
                file_obj.save()
                trash_item.delete()
                restored_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully restored {restored_count} files',
                'restored_count': restored_count
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def permanent_delete_file(request, file_id):
    """Permanently delete file from trash"""
    if request.method == 'POST':
        try:
            file_obj = get_object_or_404(File, id=file_id, owner=request.user, is_deleted=True)
            trash_item = get_object_or_404(Trash, file=file_obj, user=request.user)
            
            # Delete the actual file from storage
            file_obj.file.delete(save=False)
            
            # Delete the database records
            trash_item.delete()
            file_obj.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'File permanently deleted'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def empty_trash(request):
    """Permanently delete all files in trash"""
    if request.method == 'POST':
        try:
            trash_items = Trash.objects.filter(user=request.user)
            deleted_count = 0
            
            for trash_item in trash_items:
                file_obj = trash_item.file
                
                # Delete the actual file from storage
                file_obj.file.delete(save=False)
                
                # Delete the database records
                trash_item.delete()
                file_obj.delete()
                deleted_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully deleted {deleted_count} files',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})    


# TASK MANAGEMENT VIEWS

@login_required
def task_list(request):
    """View to display all tasks for the user"""
    tasks = Task.objects.filter(owner=request.user).order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    # Filter by priority if provided
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    context = {
        'tasks': tasks,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'total_tasks': Task.objects.filter(owner=request.user).count(),
        'pending_tasks': Task.objects.filter(owner=request.user, status='pending').count(),
        'completed_tasks': Task.objects.filter(owner=request.user, status='completed').count(),
        'today': timezone.now().date(),  
    }
    return render(request, 'tasks/task_list.html', context)

@login_required
def create_task(request):
    """Create a new task"""
    if request.method == 'POST':
        form = TaskCreateForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.owner = request.user
            task.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Task created successfully',
                    'task_id': str(task.id)
                })
            return redirect('task_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': form.errors
                })
    else:
        form = TaskCreateForm()
    
    return render(request, 'tasks/create_task.html', {'form': form})

@login_required
def edit_task(request, task_id):
    """Edit an existing task"""
    task = get_object_or_404(Task, id=task_id, owner=request.user)
    
    if request.method == 'POST':
        form = TaskEditForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Task updated successfully'
                })
            return redirect('task_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': form.errors
                })
    else:
        form = TaskEditForm(instance=task)
    
    return render(request, 'tasks/edit_task.html', {'form': form, 'task': task})

@login_required
def toggle_task_status(request, task_id):
    """Toggle task status between pending and completed"""
    if request.method == 'POST':
        try:
            task = get_object_or_404(Task, id=task_id, owner=request.user)
            
            if task.status == 'completed':
                task.status = 'pending'
                task.completed_at = None
            else:
                task.status = 'completed'
                task.completed_at = timezone.now()
            
            task.save()
            
            return JsonResponse({
                'success': True,
                'status': task.status,
                'status_display': task.get_status_display(),
                'completed_at': task.completed_at.isoformat() if task.completed_at else None
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def delete_task(request, task_id):
    """Delete a task"""
    if request.method == 'POST':
        try:
            task = get_object_or_404(Task, id=task_id, owner=request.user)
            task.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Task deleted successfully'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def task_detail(request, task_id):
    """View task details"""
    task = get_object_or_404(Task, id=task_id, owner=request.user)
    return render(request, 'tasks/task_detail.html', {'task': task})

@login_required
def update_task_status(request, task_id):
    """Update task status to a specific value"""
    if request.method == 'POST':
        try:
            task = get_object_or_404(Task, id=task_id, owner=request.user)
            new_status = request.POST.get('status')
            
            if new_status in dict(Task.STATUS_CHOICES):
                task.status = new_status
                if new_status == 'completed':
                    task.completed_at = timezone.now()
                else:
                    task.completed_at = None
                
                task.save()
                
                return JsonResponse({
                    'success': True,
                    'status': task.status,
                    'status_display': task.get_status_display(),
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None
                })
            else:
                return JsonResponse({'success': False, 'error': 'Invalid status'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def task_detail_json(request, task_id):
    """Return task details as JSON for AJAX requests"""
    try:
        task = get_object_or_404(Task, id=task_id, owner=request.user)
        task_data = {
            'id': str(task.id),
            'title': task.title,
            'description': task.description,
            'priority': task.priority,
            'status': task.status,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'created_at': task.created_at.isoformat(),
            'updated_at': task.updated_at.isoformat(),
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'is_overdue': task.is_overdue(),
        }
        return JsonResponse(task_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)