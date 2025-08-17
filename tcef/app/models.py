from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_confirmed = models.BooleanField(default=False)
    email_confirmation_token = models.CharField(max_length=100, unique=True, blank=True)
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {'Confirmado' if self.email_confirmed else 'Pendiente'}"

    def generate_confirmation_token(self):
        """Genera un token único para confirmación de email"""
        self.email_confirmation_token = str(uuid.uuid4())
        self.save()
        return self.email_confirmation_token

    def confirm_email(self):
        """Confirma el email del usuario"""
        self.email_confirmed = True
        self.email_confirmation_token = ""
        self.save()

    def accept_terms(self):
        """Acepta los términos y condiciones"""
        self.terms_accepted = True
        self.terms_accepted_date = timezone.now()
        self.save()

class ExerciseLog(models.Model):
    DIFFICULTY_CHOICES = [
        ('facil', 'Fácil'),
        ('medio', 'Medio'),
        ('dificil', 'Difícil'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exercise_logs')
    exercise_date = models.DateField(unique=True)  # Un check por día por usuario
    completed_at = models.DateTimeField(auto_now_add=True)  # Timestamp del check
    notes = models.TextField(blank=True, null=True, help_text="Notas sobre la rutina completada")
    difficulty = models.CharField(
        max_length=10, 
        choices=DIFFICULTY_CHOICES, 
        default='medio',
        help_text="Nivel de dificultad de la rutina"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'exercise_date']  # Un usuario solo puede tener un check por día
        ordering = ['-exercise_date']
        verbose_name = 'Registro de Ejercicio'
        verbose_name_plural = 'Registros de Ejercicios'
    
    def __str__(self):
        return f"{self.user.username} - {self.exercise_date} ({self.get_difficulty_display()})"
    
    @classmethod
    def get_month_exercises(cls, user, year, month):
        """Obtiene todos los ejercicios de un mes específico para un usuario"""
        from datetime import date
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        return cls.objects.filter(
            user=user,
            exercise_date__gte=start_date,
            exercise_date__lt=end_date
        )
    
    @classmethod
    def get_user_stats(cls, user):
        """Obtiene estadísticas del usuario"""
        total_exercises = cls.objects.filter(user=user).count()
        current_streak = cls.get_current_streak(user)
        longest_streak = cls.get_longest_streak(user)
        
        return {
            'total_exercises': total_exercises,
            'current_streak': current_streak,
            'longest_streak': longest_streak,
        }
    
    @classmethod
    def get_current_streak(cls, user):
        """Calcula la racha actual de días consecutivos"""
        from datetime import date, timedelta
        
        today = date.today()
        streak = 0
        current_date = today
        
        while True:
            if cls.objects.filter(user=user, exercise_date=current_date).exists():
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    @classmethod
    def get_longest_streak(cls, user):
        """Calcula la racha más larga de días consecutivos"""
        from datetime import date, timedelta
        
        exercises = cls.objects.filter(user=user).order_by('exercise_date')
        if not exercises:
            return 0
        
        longest_streak = 1
        current_streak = 1
        prev_date = exercises[0].exercise_date
        
        for exercise in exercises[1:]:
            if (exercise.exercise_date - prev_date).days == 1:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 1
            prev_date = exercise.exercise_date
        
        return longest_streak

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
