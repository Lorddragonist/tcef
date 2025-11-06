from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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

