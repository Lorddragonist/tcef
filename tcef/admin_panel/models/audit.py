from django.db import models
from django.contrib.auth.models import User


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

