from django.db import models


class WeeklyRoutine(models.Model):
    DAY_CHOICES = [
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miercoles', 'Miércoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sabado', 'Sábado'),
        ('domingo', 'Domingo'),
    ]
    
    day = models.CharField(
        max_length=10,
        choices=DAY_CHOICES,
        unique=True,
        help_text="Día de la semana para esta rutina"
    )
    title = models.CharField(
        max_length=100,
        help_text="Título de la rutina del día"
    )
    description = models.TextField(
        help_text="Descripción detallada de la rutina"
    )
    video_url = models.URLField(
        help_text="URL del video en GCP Cloud Storage"
    )
    duration = models.PositiveIntegerField(
        help_text="Duración del video en segundos"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indica si la rutina está activa"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['day']
        verbose_name = 'Rutina Semanal'
        verbose_name_plural = 'Rutinas Semanales'
    
    def __str__(self):
        return f"{self.get_day_display()} - {self.title}"
    
    @classmethod
    def get_today_routine(cls):
        """Obtiene la rutina del día actual"""
        from datetime import datetime
        import locale
        
        # Configurar locale para español
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
            except:
                pass
        
        today = datetime.now().strftime('%A').lower()
        
        # Mapear días en inglés a español
        day_mapping = {
            'monday': 'lunes',
            'tuesday': 'martes', 
            'wednesday': 'miercoles',
            'thursday': 'jueves',
            'friday': 'viernes',
            'saturday': 'sabado',
            'sunday': 'domingo'
        }
        
        current_day = day_mapping.get(today, 'lunes')
        
        try:
            return cls.objects.get(day=current_day, is_active=True)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_all_active_routines(cls):
        """Obtiene todas las rutinas activas ordenadas por día"""
        return cls.objects.filter(is_active=True).order_by('day')
    
    def get_duration_formatted(self):
        """Retorna la duración formateada en minutos:segundos"""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
    
    def get_next_day(self):
        """Obtiene el siguiente día de la semana"""
        day_order = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
        try:
            current_index = day_order.index(self.day)
            next_index = (current_index + 1) % 7
            return day_order[next_index]
        except ValueError:
            return 'lunes'
    
    def get_previous_day(self):
        """Obtiene el día anterior de la semana"""
        day_order = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
        try:
            current_index = day_order.index(self.day)
            previous_index = (current_index - 1) % 7
            return day_order[previous_index]
        except ValueError:
            return 'domingo'

