from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


class FoodDiary(models.Model):
    MEAL_TYPE_CHOICES = [
        ('desayuno', 'Desayuno'),
        ('almuerzo', 'Almuerzo'),
        ('cena', 'Cena'),
        ('snack', 'Snack'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='food_diary_entries')
    meal_date = models.DateField(help_text="Fecha de la comida")
    meal_time = models.TimeField(help_text="Hora de la comida")
    meal_type = models.CharField(
        max_length=20,
        choices=MEAL_TYPE_CHOICES,
        help_text="Tipo de comida"
    )
    description = models.TextField(help_text="Descripción de la comida")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Entrada de Diario de Alimentación'
        verbose_name_plural = 'Entradas de Diario de Alimentación'
        ordering = ['-meal_date', '-meal_time']
        indexes = [
            models.Index(fields=['user', 'meal_date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_meal_type_display()} - {self.meal_date} {self.meal_time}"
    
    def clean(self):
        """Validar reglas de negocio"""
        # Solo validar si el usuario está asignado (tiene un ID)
        try:
            if not self.user or not self.user.pk:
                return
        except (AttributeError, ValueError):
            return
        
        # Validar límite de comidas por tipo por día
        if self.meal_type == 'snack':
            # Snack: máximo 2 por día
            existing_snacks = FoodDiary.objects.filter(
                user=self.user,
                meal_date=self.meal_date,
                meal_type='snack'
            )
            if self.pk:
                existing_snacks = existing_snacks.exclude(pk=self.pk)
            if existing_snacks.count() >= 2:
                raise ValidationError({
                    'meal_type': 'Ya has registrado el máximo de 2 snacks para este día.'
                })
        else:
            # Desayuno, almuerzo, cena: máximo 1 por día
            existing_meal = FoodDiary.objects.filter(
                user=self.user,
                meal_date=self.meal_date,
                meal_type=self.meal_type
            )
            if self.pk:
                existing_meal = existing_meal.exclude(pk=self.pk)
            if existing_meal.exists():
                raise ValidationError({
                    'meal_type': f'Ya has registrado un {self.get_meal_type_display().lower()} para este día.'
                })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_week_entries(cls, user, year, week):
        """Obtiene todas las entradas de una semana específica"""
        from datetime import date, timedelta
        
        # Calcular el primer día de la semana (lunes)
        jan1 = date(year, 1, 1)
        days_offset = (jan1.weekday() + 1) % 7  # Ajustar para que lunes sea 0
        first_monday = jan1 - timedelta(days=days_offset)
        
        # Calcular la fecha del lunes de la semana solicitada
        week_start = first_monday + timedelta(weeks=week - 1)
        week_end = week_start + timedelta(days=6)
        
        return cls.objects.filter(
            user=user,
            meal_date__gte=week_start,
            meal_date__lte=week_end
        ).order_by('meal_date', 'meal_time')
    
    @classmethod
    def get_current_week_number(cls, date_obj=None):
        """Obtiene el número de semana del año para una fecha (ISO 8601)"""
        from datetime import date, timedelta
        
        if date_obj is None:
            date_obj = date.today()
        
        # ISO 8601: Semana comienza en lunes, primera semana contiene el 4 de enero
        jan4 = date(date_obj.year, 1, 4)
        jan4_weekday = jan4.weekday()  # 0=Lunes, 6=Domingo
        
        # Calcular el lunes de la semana que contiene el 4 de enero
        first_monday = jan4 - timedelta(days=jan4_weekday)
        
        # Calcular la diferencia en días desde el primer lunes
        days_diff = (date_obj - first_monday).days
        
        # Calcular el número de semana (1-indexed)
        if days_diff < 0:
            # Si la fecha está antes del primer lunes, calcular semana del año anterior
            prev_jan4 = date(date_obj.year - 1, 1, 4)
            prev_jan4_weekday = prev_jan4.weekday()
            prev_first_monday = prev_jan4 - timedelta(days=prev_jan4_weekday)
            days_diff = (date_obj - prev_first_monday).days
            week_number = (days_diff // 7) + 1
        else:
            week_number = (days_diff // 7) + 1
        
        return week_number
    
    @classmethod
    def get_week_dates(cls, year, week):
        """Obtiene las fechas de inicio y fin de una semana específica (ISO 8601)"""
        from datetime import date, timedelta
        
        # ISO 8601: Semana comienza en lunes, primera semana contiene el 4 de enero
        jan4 = date(year, 1, 4)
        jan4_weekday = jan4.weekday()  # 0=Lunes, 6=Domingo
        
        # Calcular el lunes de la semana que contiene el 4 de enero
        first_monday = jan4 - timedelta(days=jan4_weekday)
        
        # Calcular la fecha del lunes de la semana solicitada
        week_start = first_monday + timedelta(weeks=week - 1)
        week_end = week_start + timedelta(days=6)
        
        return week_start, week_end

