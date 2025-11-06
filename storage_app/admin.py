from django.contrib import admin
from .models import StoragePlan, UserProfile, File, ShareLink

@admin.register(StoragePlan)
class StoragePlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_storage_size', 'price']
    list_editable = ['max_storage_size', 'price']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'storage_plan', 'used_storage']
    list_filter = ['storage_plan']

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'file_type', 'size', 'uploaded_at', 'is_public']
    list_filter = ['file_type', 'is_public', 'uploaded_at']
    search_fields = ['name', 'owner__username']

@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ['file', 'token', 'created_at', 'expires_at', 'is_active']
    list_filter = ['is_active', 'created_at']