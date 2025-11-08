from django.contrib import admin
from .models import StoragePlan, UserProfile, File, ShareLink, Folder, Subscription

# Traditional registration method (more reliable)
class StoragePlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_storage_size', 'price', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    
    # Make completely read-only
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_storage_plan', 'used_storage_formatted']
    list_filter = ['storage_plan']
    search_fields = ['user__username', 'user__email']
    
    # Make completely read-only
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    # Custom display methods for read-only view
    def get_storage_plan(self, obj):
        if obj.storage_plan:
            return f"{obj.storage_plan.name} (Rs.{obj.storage_plan.price})"
        return "No Plan"
    get_storage_plan.short_description = 'Storage Plan'
    
    def used_storage_formatted(self, obj):
        # Convert bytes to human readable format
        if obj.used_storage >= 1024*1024*1024:  # GB
            return f"{obj.used_storage / (1024*1024*1024):.1f} GB"
        elif obj.used_storage >= 1024*1024:  # MB
            return f"{obj.used_storage / (1024*1024):.1f} MB"
        elif obj.used_storage >= 1024:  # KB
            return f"{obj.used_storage / 1024:.1f} KB"
        else:
            return f"{obj.used_storage} Bytes"
    used_storage_formatted.short_description = 'Used Storage'

class FileAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'file_type', 'size_formatted', 'uploaded_at', 'is_public']
    list_filter = ['file_type', 'is_public', 'uploaded_at']
    search_fields = ['name', 'owner__username']
    
    # Make completely read-only
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    # Custom display methods
    def size_formatted(self, obj):
        # Convert bytes to human readable format
        if obj.size >= 1024*1024*1024:  # GB
            return f"{obj.size / (1024*1024*1024):.1f} GB"
        elif obj.size >= 1024*1024:  # MB
            return f"{obj.size / (1024*1024):.1f} MB"
        elif obj.size >= 1024:  # KB
            return f"{obj.size / 1024:.1f} KB"
        else:
            return f"{obj.size} Bytes"
    size_formatted.short_description = 'Size'

class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ['file', 'token_short', 'created_at', 'expires_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['file__name', 'token']
    
    # Make completely read-only
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    # Custom display methods
    def token_short(self, obj):
        return str(obj.token)[:8] + "..."  # Show first 8 characters of token
    token_short.short_description = 'Token'

class FolderAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'created_at', 'files_count', 'subfolders_count']
    list_filter = ['created_at']
    search_fields = ['name', 'owner__username']
    
    # Make completely read-only
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    # Custom display methods
    def files_count(self, obj):
        return obj.files.count()
    files_count.short_description = 'Files Count'
    
    def subfolders_count(self, obj):
        return obj.subfolders.count()
    subfolders_count.short_description = 'Subfolders Count'

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'current_period_start', 'current_period_end']
    list_filter = ['status', 'plan']
    search_fields = ['user__username', 'stripe_subscription_id']
    
    # Make completely read-only
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

# Register all models using traditional method
admin.site.register(StoragePlan, StoragePlanAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(ShareLink, ShareLinkAdmin)
admin.site.register(Folder, FolderAdmin)
admin.site.register(Subscription, SubscriptionAdmin)



















# from django.contrib import admin
# from .models import StoragePlan, UserProfile, File, ShareLink

# @admin.register(StoragePlan)
# class StoragePlanAdmin(admin.ModelAdmin):
#     list_display = ['name', 'max_storage_size', 'price']
#     list_editable = ['max_storage_size', 'price']

# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ['user', 'storage_plan', 'used_storage']
#     list_filter = ['storage_plan']

# @admin.register(File)
# class FileAdmin(admin.ModelAdmin):
#     list_display = ['name', 'owner', 'file_type', 'size', 'uploaded_at', 'is_public']
#     list_filter = ['file_type', 'is_public', 'uploaded_at']
#     search_fields = ['name', 'owner__username']

# @admin.register(ShareLink)
# class ShareLinkAdmin(admin.ModelAdmin):
#     list_display = ['file', 'token', 'created_at', 'expires_at', 'is_active']
#     list_filter = ['is_active', 'created_at']