from django.contrib import admin
from .models import UserGroup, UserGroupMembership, CustomRoutine, AdminActivity, VideoUploadSession, UserApprovalRequest, PasswordResetApproval, Video, RoutineVideo


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
    list_display = ['title', 'group', 'assigned_date', 'get_videos_count', 'get_total_duration', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'assigned_date', 'group', 'created_at']
    search_fields = ['title', 'description', 'group__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-assigned_date']
    
    fieldsets = (
        ('Información de la Rutina', {
            'fields': ('title', 'description')
        }),
        ('Asignación', {
            'fields': ('group', 'assigned_date', 'is_active')
        }),
        ('Metadatos', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'filename', 'get_duration_formatted', 'get_file_size_formatted', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at', 'created_by']
    search_fields = ['title', 'description', 'filename']
    readonly_fields = ['filename', 's3_key', 's3_url', 'file_size', 'upload_session', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información del Video', {
            'fields': ('title', 'description', 'filename', 'duration')
        }),
        ('Archivo', {
            'fields': ('s3_key', 's3_url', 'file_size', 'upload_session')
        }),
        ('Configuración', {
            'fields': ('thumbnail_url', 'is_active')
        }),
        ('Metadatos', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RoutineVideo)
class RoutineVideoAdmin(admin.ModelAdmin):
    list_display = ['routine', 'video', 'order', 'created_at']
    list_filter = ['routine__group', 'routine__assigned_date', 'created_at']
    search_fields = ['routine__title', 'video__title', 'notes']
    readonly_fields = ['created_at']
    ordering = ['routine', 'order']
    
    fieldsets = (
        ('Asignación', {
            'fields': ('routine', 'video', 'order')
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Metadatos', {
            'fields': ('created_at',),
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
    readonly_fields = ['admin_user', 'filename', 'file_size', 's3_bucket', 's3_key', 'started_at']
    ordering = ['-started_at']
    
    fieldsets = (
        ('Información del Archivo', {
            'fields': ('filename', 'file_size', 's3_bucket', 's3_key')
        }),
        ('Estado de la Subida', {
            'fields': ('status', 'progress', 'error_message')
        }),
        ('Metadatos', {
            'fields': ('admin_user', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserApprovalRequest)
class UserApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'requested_at', 'reviewed_at', 'reviewed_by']
    list_filter = ['status', 'requested_at', 'reviewed_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['user', 'requested_at']
    ordering = ['-requested_at']
    
    fieldsets = (
        ('Información del Usuario', {
            'fields': ('user', 'status', 'requested_at')
        }),
        ('Revisión', {
            'fields': ('reviewed_at', 'reviewed_by', 'notes')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'approved':
                obj.approve(request.user, obj.notes)
            elif obj.status == 'rejected':
                obj.reject(request.user, obj.notes)
        super().save_model(request, obj, form, change)


@admin.register(PasswordResetApproval)
class PasswordResetApprovalAdmin(admin.ModelAdmin):
    list_display = ['reset_request', 'status', 'reviewed_at', 'reviewed_by']
    list_filter = ['status', 'reviewed_at']
    search_fields = ['reset_request__user__username', 'reset_request__user__email']
    readonly_fields = ['reset_request', 'reviewed_at']
    ordering = ['-reviewed_at']
    
    fieldsets = (
        ('Solicitud de Reseteo', {
            'fields': ('reset_request', 'status')
        }),
        ('Revisión', {
            'fields': ('reviewed_at', 'reviewed_by', 'notes')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'approved':
                obj.approve(request.user, obj.notes)
            elif obj.status == 'rejected':
                obj.reject(request.user, obj.notes)
        super().save_model(request, obj, form, change)
