from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.models import BodyMeasurements, BodyCompositionHistory
from datetime import date, timedelta
import math
import random

class Command(BaseCommand):
    help = 'Create historical measurement data for testing charts'

    def handle(self, *args, **options):
        # Obtener usuarios con perfil aprobado
        users = User.objects.filter(userprofile__is_approved=True)
        
        for user in users:
            self.stdout.write(f"\n--- Creando datos históricos para: {user.username} ---")
            
            # Obtener medidas existentes
            existing_measurements = BodyMeasurements.objects.filter(user=user).order_by('-measurement_date')
            
            if not existing_measurements.exists():
                self.stdout.write(f"  No hay medidas para {user.username}, saltando...")
                continue
                
            latest_measurement = existing_measurements.first()
            
            # Crear datos históricos (últimos 3 meses)
            base_date = date.today() - timedelta(days=90)
            
            for i in range(5):  # Crear 5 puntos de datos
                measurement_date = base_date + timedelta(days=i * 15)  # Cada 15 días
                
                # Verificar si ya existe una medida para esta fecha
                if BodyMeasurements.objects.filter(user=user, measurement_date=measurement_date).exists():
                    continue
                
                # Crear variaciones realistas en los datos
                weight_variation = random.uniform(-2, 2)  # ±2kg
                waist_variation = random.uniform(-1, 1)  # ±1cm
                hip_variation = random.uniform(-1, 1)    # ±1cm
                chest_variation = random.uniform(-0.5, 0.5)  # ±0.5cm
                
                new_weight = max(50, float(latest_measurement.weight) + weight_variation)
                new_waist = max(60, float(latest_measurement.waist) + waist_variation)
                new_hip = max(80, float(latest_measurement.hip) + hip_variation)
                new_chest = max(30, float(latest_measurement.chest) + chest_variation)
                
                # Crear medida básica
                measurement = BodyMeasurements.objects.create(
                    user=user,
                    measurement_date=measurement_date,
                    weight=new_weight,
                    height=latest_measurement.height,
                    age=latest_measurement.age,
                    waist=new_waist,
                    hip=new_hip,
                    chest=new_chest
                )
                
                # Obtener género del usuario
                user_gender = getattr(user.userprofile, 'gender', 'M') if hasattr(user, 'userprofile') else 'M'
                
                # Calcular composición corporal
                height_m = float(measurement.height) / 100
                imc = round(new_weight / (height_m ** 2), 2)
                ica = round(new_waist / float(measurement.height), 2)
                
                body_fat_percentage = self.calculate_body_fat_us_navy(
                    new_weight, float(measurement.height), new_waist, 
                    new_hip, new_chest, measurement.age, user_gender
                )
                
                muscle_mass = round(new_weight * (100 - body_fat_percentage) / 100, 1)
                
                # Crear composición corporal
                BodyCompositionHistory.objects.create(
                    user=user,
                    measurement_date=measurement_date,
                    imc=imc,
                    ica=ica,
                    body_fat_percentage=round(body_fat_percentage, 1),
                    muscle_mass=muscle_mass
                )
                
                self.stdout.write(f"  ✅ Creado: {measurement_date} - Peso: {new_weight:.1f}kg, IMC: {imc}, % Grasa: {body_fat_percentage:.1f}%")

    def calculate_body_fat_us_navy(self, weight, height, waist, hip, neck, age, gender):
        """Calcula % de grasa corporal usando fórmula US Navy"""
        try:
            if gender == 'M':  # Hombre
                if waist <= neck:
                    return 0
                body_fat = 495 / (1.0324 - 0.19077 * math.log10(waist - neck) + 0.15456 * math.log10(height)) - 450
            else:  # Mujer
                if (waist + hip) <= neck:
                    return 0
                body_fat = 495 / (1.29579 - 0.35004 * math.log10(waist + hip - neck) + 0.22100 * math.log10(height)) - 450
            
            return max(0, min(100, body_fat))
        except (ValueError, ZeroDivisionError):
            return 0
