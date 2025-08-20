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
    
    # Subida de videos
    path('videos/upload/', views.video_upload, name='video_upload'),
    
    # Monitoreo de usuarios
    path('monitoring/', views.user_monitoring, name='user_monitoring'),
    
    # Registro de actividades
    path('activities/', views.admin_activity_log, name='activity_log'),
] 