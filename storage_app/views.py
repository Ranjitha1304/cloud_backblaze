from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Sum
from django.utils import timezone
import os
from .models import File, UserProfile, ShareLink, StoragePlan, Folder
from .forms import CustomUserCreationForm, FileUploadForm, FileShareForm, FolderCreateForm, MoveFileForm

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
    user_profile = UserProfile.objects.get(user=request.user)
    files = File.objects.filter(owner=request.user).order_by('-uploaded_at')
    total_files = files.count()
    
    # Calculate storage usage
    total_size = files.aggregate(Sum('size'))['size__sum'] or 0
    user_profile.used_storage = total_size
    user_profile.save()
    
    context = {
        'user_profile': user_profile,
        'files': files[:10],
        'total_files': total_files,
        'total_size': total_size,
        'storage_usage_percent': user_profile.get_storage_usage_percent(),
    }
    return render(request, 'dashboard.html', context)

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
    if request.method == 'POST':
        file = get_object_or_404(File, id=file_id, owner=request.user)
        # For cloud storage, we don't need to delete local file
        file.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

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
    """File list with folder support"""
    current_folder = None
    if folder_id:
        current_folder = get_object_or_404(Folder, id=folder_id, owner=request.user)
    
    # Get files in current folder
    files = File.objects.filter(owner=request.user, folder=current_folder).order_by('-uploaded_at')
    
    # Get folders in current folder
    folders = Folder.objects.filter(owner=request.user, parent_folder=current_folder).order_by('name')
    
    # Get all folders for move dropdown
    all_folders = Folder.objects.filter(owner=request.user).exclude(id=current_folder.id if current_folder else None)
    
    # Folder creation form
    folder_form = FolderCreateForm()
    
    context = {
        'files': files,
        'folders': folders,
        'current_folder': current_folder,
        'all_folders': all_folders,
        'folder_form': folder_form,
    }
    return render(request, 'file_list.html', context)

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