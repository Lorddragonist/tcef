from django.db import models
from django.contrib.auth.models import User
from datetime import date


class CustomRoutine(models.Model):
    """Rutina personalizada asignada a un grupo en una fecha específica"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    group = models.ForeignKey('admin_panel.UserGroup', on_delete=models.CASCADE, related_name='routines')
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

    def get_total_duration(self):
        """Retorna la duración total de todos los videos de la rutina"""
        total_seconds = sum(rv.video.duration for rv in self.routine_videos.all())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def get_videos_count(self):
        """Retorna el número de videos en la rutina"""
        return self.routine_videos.count()

    def get_videos_ordered(self):
        """Retorna los videos ordenados por el campo order"""
        return self.routine_videos.select_related('video').order_by('order')


class RoutineVideo(models.Model):
    """Relación entre rutinas y videos con orden específico"""
    routine = models.ForeignKey(CustomRoutine, on_delete=models.CASCADE, related_name='routine_videos')
    video = models.ForeignKey('admin_panel.Video', on_delete=models.CASCADE, related_name='routine_assignments')
    order = models.PositiveIntegerField(help_text='Orden del video en la rutina (1, 2, 3, etc.)')
    notes = models.TextField(blank=True, help_text='Notas específicas para este video en la rutina')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Video de Rutina'
        verbose_name_plural = 'Videos de Rutina'
        unique_together = ['routine', 'order']
        ordering = ['order']

    def __str__(self):
        return f"{self.routine.title} - Video {self.order}: {self.video.title}"

