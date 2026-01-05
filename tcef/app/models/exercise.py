from django.db import models
from django.contrib.auth.models import User


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
        """Calcula la última racha de semanas con 5+ rutinas obtenida (sin límite de año)"""
        from datetime import date, timedelta
        
        today = date.today()
        streak = 0
        current_week_start = today - timedelta(days=today.weekday())
        
        # Límite de seguridad: máximo 10 años hacia atrás
        min_date = date(today.year - 10, 1, 1)
        min_week_start = min_date - timedelta(days=min_date.weekday())
        
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
            
            while current_week_start >= min_week_start:
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
            # Si la semana actual tiene 5+ rutinas, contar desde ahí hacia atrás
            while current_week_start >= min_week_start:
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
        """Calcula la racha más larga de semanas con 5+ rutinas (sin límite de año)"""
        from datetime import date, timedelta
        
        exercises = cls.objects.filter(user=user).order_by('exercise_date')
        if not exercises:
            return 0
        
        # Obtener el rango completo de fechas con ejercicios
        first_exercise = exercises.first().exercise_date
        last_exercise = exercises.last().exercise_date
        
        # Límite de seguridad: máximo 10 años hacia atrás desde hoy
        today = date.today()
        min_date = date(today.year - 10, 1, 1)
        
        # Asegurar que no vayamos más atrás del límite
        if first_exercise < min_date:
            first_exercise = min_date
        
        # Calcular todas las semanas desde la primera hasta la última
        # Empezar desde el lunes de la semana que contiene el primer ejercicio
        first_week_start = first_exercise - timedelta(days=first_exercise.weekday())
        last_week_start = last_exercise - timedelta(days=last_exercise.weekday())
        
        # Iterar semana por semana desde la primera hasta la última
        current_week_start = first_week_start
        longest_streak = 0
        current_streak = 0
        
        while current_week_start <= last_week_start:
            week_end = current_week_start + timedelta(days=6)
            
            # Contar ejercicios de esta semana
            week_count = cls.objects.filter(
                user=user,
                exercise_date__gte=current_week_start,
                exercise_date__lte=week_end
            ).count()
            
            # Si la semana tiene 5+ ejercicios, incrementar la racha
            if week_count >= 5:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                # Si no tiene 5+ ejercicios, reiniciar la racha
                current_streak = 0
            
            # Avanzar a la siguiente semana
            current_week_start += timedelta(weeks=1)
        
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

