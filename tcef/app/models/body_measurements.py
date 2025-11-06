from django.db import models
from django.contrib.auth.models import User


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

