from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False, help_text="Usuario aprobado por el administrador")
    approval_date = models.DateTimeField(null=True, blank=True, help_text="Fecha de aprobación")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_users', help_text="Administrador que aprobó al usuario")
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_date = models.DateTimeField(null=True, blank=True)
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        null=True,
        blank=True,
        verbose_name="Sexo",
        help_text="Sexo del usuario"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {'Aprobado' if self.is_approved else 'Pendiente de Aprobación'}"

    def approve_user(self, admin_user):
        """Aprueba al usuario por parte del administrador"""
        self.is_approved = True
        self.approval_date = timezone.now()
        self.approved_by = admin_user
        self.save()
        
        # Activar la cuenta del usuario
        self.user.is_active = True
        self.user.save()

    def accept_terms(self):
        """Acepta los términos y condiciones"""
        self.terms_accepted = True
        self.terms_accepted_date = timezone.now()
        self.save()


class PasswordResetRequest(models.Model):
    """Solicitud de reseteo de contraseña que debe ser aprobada por el admin"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
        ('completed', 'Completada'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_resets')
    reset_token = models.CharField(max_length=100, unique=True, blank=True, null=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Notas del administrador")
    
    class Meta:
        verbose_name = 'Solicitud de Reseteo de Contraseña'
        verbose_name_plural = 'Solicitudes de Reseteo de Contraseña'
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()} - {self.requested_at}"
    
    def approve_request(self, admin_user, notes=""):
        """Aprueba la solicitud de reseteo y genera un token único"""
        import uuid
        from datetime import timedelta
        
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.approved_by = admin_user
        self.notes = notes
        self.reset_token = str(uuid.uuid4())
        self.token_expires_at = timezone.now() + timedelta(hours=24)  # Token válido por 24 horas
        self.save()
    
    def reject_request(self, admin_user, notes=""):
        """Rechaza la solicitud de reseteo"""
        self.status = 'rejected'
        self.approved_by = admin_user
        self.notes = notes
        self.save()
    
    def complete_reset(self):
        """Marca el reseteo como completado"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def is_token_valid(self):
        """Verifica si el token de reseteo es válido y no ha expirado"""
        if not self.reset_token or self.status != 'approved':
            return False
        if self.token_expires_at and timezone.now() > self.token_expires_at:
            return False
        return True

