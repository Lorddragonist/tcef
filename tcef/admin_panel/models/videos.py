from django.db import models
from django.contrib.auth.models import User


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
    s3_bucket = models.CharField(max_length=100)
    s3_key = models.CharField(max_length=255, blank=True)
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


class Video(models.Model):
    """Modelo para almacenar información de videos subidos a S3"""
    title = models.CharField(max_length=200, help_text='Título del video')
    description = models.TextField(blank=True, help_text='Descripción del video')
    filename = models.CharField(max_length=255, help_text='Nombre original del archivo')
    s3_key = models.CharField(max_length=500, help_text='Clave S3 del video')
    s3_url = models.URLField(help_text='URL pública del video en S3')
    thumbnail_url = models.URLField(blank=True, null=True, help_text='URL de la imagen miniatura')
    duration = models.PositiveIntegerField(help_text='Duración en segundos')
    file_size = models.BigIntegerField(help_text='Tamaño del archivo en bytes')
    upload_session = models.OneToOneField(VideoUploadSession, on_delete=models.CASCADE, related_name='video')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_videos')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Video'
        verbose_name_plural = 'Videos'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.filename})"

    def get_duration_formatted(self):
        """Retorna la duración formateada en minutos:segundos"""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"

    def get_file_size_formatted(self):
        """Retorna el tamaño del archivo formateado"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

