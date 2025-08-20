from django.contrib import admin
from .models import UserGroup, UserGroupMembership, CustomRoutine, AdminActivity, VideoUploadSession


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'color', 'is_active', 'get_member_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'color', 'is_active')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserGroupMembership)
class UserGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'joined_at', 'is_active']
    list_filter = ['is_active', 'joined_at', 'group']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'group__name']
    readonly_fields = ['joined_at']
    ordering = ['-joined_at']


@admin.register(CustomRoutine)
class CustomRoutineAdmin(admin.ModelAdmin):
    list_display = ['title', 'group', 'assigned_date', 'duration', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'assigned_date', 'group', 'created_at']
    search_fields = ['title', 'description', 'group__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-assigned_date']
    
    fieldsets = (
        ('Información de la Rutina', {
            'fields': ('title', 'description', 'video_url', 'thumbnail_url', 'duration')
        }),
        ('Asignación', {
            'fields': ('group', 'assigned_date', 'is_active')
        }),
        ('Metadatos', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AdminActivity)
class AdminActivityAdmin(admin.ModelAdmin):
    list_display = ['admin_user', 'action', 'target_model', 'target_id', 'created_at']
    list_filter = ['action', 'target_model', 'created_at', 'admin_user']
    search_fields = ['admin_user__username', 'details']
    readonly_fields = ['admin_user', 'action', 'target_model', 'target_id', 'details', 'ip_address', 'user_agent', 'created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Actividad', {
            'fields': ('admin_user', 'action', 'target_model', 'target_id', 'details')
        }),
        ('Información Técnica', {
            'fields': ('ip_address', 'user_agent', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(VideoUploadSession)
class VideoUploadSessionAdmin(admin.ModelAdmin):
    list_display = ['filename', 'admin_user', 'status', 'progress', 'file_size', 'started_at']
    list_filter = ['status', 'started_at', 'admin_user']
    search_fields = ['filename', 'admin_user__username']
    readonly_fields = ['admin_user', 'filename', 'file_size', 'gcp_bucket', 'gcp_blob_name', 'started_at']
    ordering = ['-started_at']
    
    fieldsets = (
        ('Información del Archivo', {
            'fields': ('filename', 'file_size', 'gcp_bucket', 'gcp_blob_name')
        }),
        ('Estado de la Subida', {
            'fields': ('status', 'progress', 'error_message')
        }),
        ('Metadatos', {
            'fields': ('admin_user', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
