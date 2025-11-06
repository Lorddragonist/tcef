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

