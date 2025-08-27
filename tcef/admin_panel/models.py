from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date


class UserGroup(models.Model):
    """Grupo de usuarios para personalizar rutinas"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text='Color del grupo en formato HEX')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Grupo de Usuarios'
        verbose_name_plural = 'Grupos de Usuarios'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_member_count(self):
        return self.members.count()


class UserGroupMembership(models.Model):
    """Relación muchos a muchos entre usuarios y grupos"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    group = models.ForeignKey(UserGroup, on_delete=models.CASCADE, related_name='members')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'group']
        verbose_name = 'Membresía de Grupo'
        verbose_name_plural = 'Membresías de Grupos'

    def __str__(self):
        return f"{self.user.username} - {self.group.name}"


class CustomRoutine(models.Model):
    """Rutina personalizada asignada a un grupo en una fecha específica"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    video_url = models.URLField(help_text='URL del video en GCP Blob Storage')
    thumbnail_url = models.URLField(blank=True, null=True, help_text='URL de la imagen miniatura')
    duration = models.PositiveIntegerField(help_text='Duración en segundos')
    group = models.ForeignKey(UserGroup, on_delete=models.CASCADE, related_name='routines')
    assigned_date = models.DateField(help_text='Fecha específica para esta rutina')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_routines')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rutina Personalizada'
        verbose_name_plural = 'Rutinas Personalizadas'
        unique_together = ['group', 'assigned_date']
        ordering = ['-assigned_date']

    def __str__(self):
        return f"{self.title} - {self.group.name} - {self.assigned_date}"

    def is_today(self):
        return self.assigned_date == date.today()

    def is_past(self):
        return self.assigned_date < date.today()

    def is_future(self):
        return self.assigned_date > date.today()


class AdminActivity(models.Model):
    """Registro de actividades administrativas para auditoría"""
    ACTION_CHOICES = [
        ('user_created', 'Usuario Creado'),
        ('user_updated', 'Usuario Actualizado'),
        ('user_deleted', 'Usuario Eliminado'),
        ('group_created', 'Grupo Creado'),
        ('group_updated', 'Grupo Actualizado'),
        ('group_deleted', 'Grupo Eliminado'),
        ('routine_created', 'Rutina Creada'),
        ('routine_updated', 'Rutina Actualizada'),
        ('routine_deleted', 'Rutina Eliminada'),
        ('video_uploaded', 'Video Subido'),
        ('video_deleted', 'Video Eliminado'),
    ]

    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_activities')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_model = models.CharField(max_length=50, help_text='Modelo afectado')
    target_id = models.PositiveIntegerField(help_text='ID del objeto afectado')
    details = models.TextField(blank=True, help_text='Detalles adicionales de la acción')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Actividad Administrativa'
        verbose_name_plural = 'Actividades Administrativas'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.admin_user.username} - {self.get_action_display()} - {self.created_at}"


class VideoUploadSession(models.Model):
    """Sesión de subida de video para tracking del proceso"""
    STATUS_CHOICES = [
        ('uploading', 'Subiendo'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
    ]

    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_uploads')
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text='Tamaño del archivo en bytes')
    gcp_bucket = models.CharField(max_length=100)
    gcp_blob_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    progress = models.PositiveIntegerField(default=0, help_text='Progreso de subida (0-100)')
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Sesión de Subida de Video'
        verbose_name_plural = 'Sesiones de Subida de Videos'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.filename} - {self.get_status_display()}"

    def is_completed(self):
        return self.status == 'completed'

    def is_failed(self):
        return self.status == 'failed'


class UserApprovalRequest(models.Model):
    """Solicitud de aprobación de usuario nuevo"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='approval_request')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_approvals')
    notes = models.TextField(blank=True, help_text="Notas del administrador")
    
    class Meta:
        verbose_name = 'Solicitud de Aprobación de Usuario'
        verbose_name_plural = 'Solicitudes de Aprobación de Usuarios'
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()}"
    
    def approve(self, admin_user, notes=""):
        """Aprueba la solicitud del usuario"""
        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.notes = notes
        self.save()
        
        # Activar el usuario y su perfil
        self.user.is_active = True
        self.user.save()
        
        try:
            profile = self.user.userprofile
            profile.approve_user(admin_user)
        except:
            pass
    
    def reject(self, admin_user, notes=""):
        """Rechaza la solicitud del usuario"""
        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.notes = notes
        self.save()


class PasswordResetApproval(models.Model):
    """Aprobación de reseteo de contraseña por admin"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
    ]
    
    reset_request = models.OneToOneField('app.PasswordResetRequest', on_delete=models.CASCADE, related_name='admin_approval')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_resets')
    notes = models.TextField(blank=True, help_text="Notas del administrador")
    
    class Meta:
        verbose_name = 'Aprobación de Reseteo de Contraseña'
        verbose_name_plural = 'Aprobaciones de Reseteo de Contraseña'
        ordering = ['-reviewed_at']
    
    def __str__(self):
        return f"{self.reset_request.user.username} - {self.get_status_display()}"
    
    def approve(self, admin_user, notes=""):
        """Aprueba el reseteo de contraseña"""
        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.notes = notes
        self.save()
        
        # Aprobar la solicitud de reseteo
        self.reset_request.approve_request(admin_user, notes)
    
    def reject(self, admin_user, notes=""):
        """Rechaza el reseteo de contraseña"""
        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.notes = notes
        self.save()
        
        # Rechazar la solicitud de reseteo
        self.reset_request.reject_request(admin_user, notes)
