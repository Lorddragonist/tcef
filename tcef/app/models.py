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
