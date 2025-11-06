from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Files with folder support
    path('files/', views.file_list, name='file_list'),
    path('files/folder/<uuid:folder_id>/', views.file_list, name='file_list_folder'),
    
    path('upload/', views.upload_file, name='upload_file'),
    path('delete/<uuid:file_id>/', views.delete_file, name='delete_file'),
    path('download/<uuid:file_id>/', views.download_file, name='download_file'),
    
    # Folder management URLs
    path('folder/create/', views.create_folder, name='create_folder'),
    path('folder/delete/<uuid:folder_id>/', views.delete_folder, name='delete_folder'),
    path('file/move/<uuid:file_id>/', views.move_file, name='move_file'),
    
    # Share URLs
    path('share/create/<uuid:file_id>/', views.create_share_link, name='create_share'),
    path('share/<uuid:token>/', views.share_file, name='share_file'),

    path('file/toggle-public/<uuid:file_id>/', views.toggle_file_visibility, name='toggle_file_visibility'),
    path('public/file/<uuid:file_id>/', views.public_file_access, name='public_file_access'),

]