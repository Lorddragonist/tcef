from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# Create your models here.

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

class ExerciseLog(models.Model):
    DIFFICULTY_CHOICES = [
        ('facil', 'Fácil'),
        ('medio', 'Medio'),
        ('dificil', 'Difícil'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exercise_logs')
    exercise_date = models.DateField()  # Removido unique=True
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
    def get_user_stats(cls, user, year=None, month=None):
        """Obtiene estadísticas del usuario"""
        from datetime import datetime, date
        import calendar
        
        # Si no se especifica año/mes, usar el actual
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month
            
        # Total de ejercicios del mes que se está mostrando
        total_exercises_this_month = cls.objects.filter(
            user=user,
            exercise_date__year=year,
            exercise_date__month=month
        ).count()
        
        # Calcular días laborales (lunes a viernes) del mes
        # Obtener el último día del mes
        last_day = calendar.monthrange(year, month)[1]
        
        weekdays_count = 0
        for day in range(1, last_day + 1):
            current_day = date(year, month, day)
            # weekday() devuelve 0 para lunes, 1 para martes, etc.
            if current_day.weekday() < 5:  # 0-4 son lunes a viernes
                weekdays_count += 1
                
        # Calcular el porcentaje de días laborales completados
        if weekdays_count > 0:
            progress_percentage = (total_exercises_this_month / weekdays_count) * 100
        else:
            progress_percentage = 0
        
        total_exercises = cls.objects.filter(user=user).count()
        current_streak = cls.get_current_week_streak(user)
        longest_streak = cls.get_longest_week_streak(user)
        
        return {
            'total_exercises': total_exercises,
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'total_exercises_this_month': total_exercises_this_month,
            'weekdays_count': weekdays_count,
            'progress_percentage': progress_percentage,
        }
    
    @classmethod
    def get_current_week_streak(cls, user):
        """Calcula la última racha de semanas con 5+ rutinas obtenida"""
        from datetime import date, timedelta
        
        today = date.today()
        streak = 0
        current_week_start = today - timedelta(days=today.weekday())
        
        # Verificar si la semana actual tiene 5+ rutinas
        week_end = current_week_start + timedelta(days=6)
        week_exercises = cls.objects.filter(
            user=user,
            exercise_date__gte=current_week_start,
            exercise_date__lte=week_end
        ).count()
        
        # Si la semana actual no tiene 5+ rutinas, buscar la última racha completa
        if week_exercises < 5:
            # Retroceder una semana y buscar la última racha completa
            current_week_start -= timedelta(weeks=1)
            
            while True:
                week_end = current_week_start + timedelta(days=6)
                week_exercises = cls.objects.filter(
                    user=user,
                    exercise_date__gte=current_week_start,
                    exercise_date__lte=week_end
                ).count()
                
                if week_exercises >= 5:
                    streak += 1
                    current_week_start -= timedelta(weeks=1)
                else:
                    break
        else:
            # Si la semana actual tiene 5+ rutinas, contar desde ahí
            while True:
                week_end = current_week_start + timedelta(days=6)
                week_exercises = cls.objects.filter(
                    user=user,
                    exercise_date__gte=current_week_start,
                    exercise_date__lte=week_end
                ).count()
                
                if week_exercises >= 5:
                    streak += 1
                    current_week_start -= timedelta(weeks=1)
                else:
                    break
        
        return streak
    
    @classmethod
    def get_longest_week_streak(cls, user):
        """Calcula la racha más larga de semanas con 5+ rutinas"""
        from datetime import date, timedelta
        
        exercises = cls.objects.filter(user=user).order_by('exercise_date')
        if not exercises:
            return 0
        
        # Obtener todas las semanas únicas con ejercicios
        week_starts = set()
        for exercise in exercises:
            week_start = exercise.exercise_date - timedelta(days=exercise.exercise_date.weekday())
            week_starts.add(week_start)
        
        week_starts = sorted(list(week_starts))
        
        longest_streak = 1
        current_streak = 1
        
        for i in range(1, len(week_starts)):
            # Verificar si las semanas son consecutivas
            expected_week = week_starts[i-1] + timedelta(weeks=1)
            if week_starts[i] == expected_week:
                # Verificar si ambas semanas tienen 5+ ejercicios
                week1_end = week_starts[i-1] + timedelta(days=6)
                week2_end = week_starts[i] + timedelta(days=6)
                
                week1_count = cls.objects.filter(
                    user=user,
                    exercise_date__gte=week_starts[i-1],
                    exercise_date__lte=week1_end
                ).count()
                
                week2_count = cls.objects.filter(
                    user=user,
                    exercise_date__gte=week_starts[i],
                    exercise_date__lte=week2_end
                ).count()
                
                if week1_count >= 5 and week2_count >= 5:
                    current_streak += 1
                    longest_streak = max(longest_streak, current_streak)
                else:
                    current_streak = 1
            else:
                current_streak = 1
        
        return longest_streak
    
    @classmethod
    def get_current_streak(cls, user):
        """Calcula la racha actual de días consecutivos con ejercicio"""
        from datetime import date, timedelta
        
        today = date.today()
        streak = 0
        current_date = today
        
        # Verificar si hoy tiene ejercicio
        if cls.objects.filter(user=user, exercise_date=current_date).exists():
            streak = 1
            current_date -= timedelta(days=1)
            
            # Continuar contando hacia atrás
            while cls.objects.filter(user=user, exercise_date=current_date).exists():
                streak += 1
                current_date -= timedelta(days=1)
        else:
            # Si hoy no tiene ejercicio, buscar la última racha
            current_date -= timedelta(days=1)
            while current_date >= date(2020, 1, 1):  # Límite razonable
                if cls.objects.filter(user=user, exercise_date=current_date).exists():
                    streak += 1
                    current_date -= timedelta(days=1)
                else:
                    break
        
        return streak
    
    @classmethod
    def get_best_streak(cls, user):
        """Calcula la mejor racha de días consecutivos con ejercicio"""
        from datetime import date, timedelta
        
        exercises = cls.objects.filter(user=user).order_by('exercise_date')
        if not exercises:
            return 0
        
        best_streak = 1
        current_streak = 1
        last_date = exercises.first().exercise_date
        
        for exercise in exercises[1:]:
            if exercise.exercise_date == last_date + timedelta(days=1):
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            else:
                current_streak = 1
            last_date = exercise.exercise_date
        
        return best_streak



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

# Agregar al final de models.py

class BodyMeasurements(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='body_measurements')
    measurement_date = models.DateField()
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Peso en kg")
    height = models.DecimalField(max_digits=5, decimal_places=2, help_text="Altura en cm")
    age = models.PositiveIntegerField(help_text="Edad en años")
    waist = models.DecimalField(max_digits=5, decimal_places=2, help_text="Cintura en cm")
    hip = models.DecimalField(max_digits=5, decimal_places=2, help_text="Cadera en cm")
    chest = models.DecimalField(max_digits=5, decimal_places=2, help_text="Cuello en cm")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-measurement_date']
        unique_together = ['user', 'measurement_date']

    def __str__(self):
        return f"{self.user.username} - {self.measurement_date}"

    @property
    def bmi(self):
        """Calcula el IMC"""
        if self.height > 0:
            height_m = self.height / 100
            return round(self.weight / (height_m ** 2), 2)
        return 0

    @property
    def waist_hip_ratio(self):
        """Calcula la relación cintura-cadera"""
        if self.hip > 0:
            return round(self.waist / self.hip, 2)
        return 0

class BodyCompositionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='body_composition_history')
    measurement_date = models.DateField()
    imc = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ica = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    body_fat_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    muscle_mass = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'measurement_date')
        ordering = ['-measurement_date']