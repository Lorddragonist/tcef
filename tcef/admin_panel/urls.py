from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Dashboard principal
    path('', views.admin_dashboard, name='dashboard'),
    
    # Gestión de usuarios
    path('users/', views.user_management, name='user_management'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    
    # Gestión de grupos
    path('groups/', views.group_management, name='group_management'),
    
    # Gestión de rutinas
    path('routines/', views.routine_management, name='routine_management'),
    path('routines/create/', views.create_routine, name='create_routine'),
    path('routines/<int:routine_id>/edit/', views.edit_routine, name='edit_routine'),
    path('routines/<int:routine_id>/delete/', views.delete_routine, name='delete_routine'),
    path('routines/<int:routine_id>/details/', views.routine_details, name='routine_details'),
    path('routines/<int:routine_id>/replicate/', views.replicate_routine, name='replicate_routine'),
    
    # Subida de videos
    path('videos/upload/', views.video_upload, name='video_upload'),
    path('videos/delete/<int:video_id>/', views.delete_video, name='delete_video'),
    
    # Monitoreo de usuarios
    path('monitoring/', views.user_monitoring, name='user_monitoring'),
    path('monitoring/user/<int:user_id>/details/', views.user_detail_modal, name='user_detail_modal'),
    
] 