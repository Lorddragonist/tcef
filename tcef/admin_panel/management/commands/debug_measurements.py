from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.models import BodyMeasurements, BodyCompositionHistory
from datetime import date, timedelta
import math

class Command(BaseCommand):
    help = 'Debug measurements data and create test data if needed'

    def handle(self, *args, **options):
        # Verificar usuarios con perfil aprobado
        users = User.objects.filter(userprofile__is_approved=True)
        self.stdout.write(f"Usuarios aprobados: {users.count()}")
        
        for user in users:
            self.stdout.write(f"\n--- Usuario: {user.username} ---")
            
            # Verificar medidas básicas
            measurements = BodyMeasurements.objects.filter(user=user).order_by('-measurement_date')
            self.stdout.write(f"Medidas básicas: {measurements.count()}")
            if measurements.exists():
                latest = measurements.first()
                self.stdout.write(f"  Última medida: {latest.measurement_date} - Peso: {latest.weight}kg, Altura: {latest.height}cm")
            
            # Verificar composición corporal
            compositions = BodyCompositionHistory.objects.filter(user=user).order_by('-measurement_date')
            self.stdout.write(f"Composición corporal: {compositions.count()}")
            if compositions.exists():
                latest = compositions.first()
                self.stdout.write(f"  Última composición: {latest.measurement_date} - IMC: {latest.imc}, % Grasa: {latest.body_fat_percentage}%, Músculo: {latest.muscle_mass}kg, ICA: {latest.ica}")
            else:
                self.stdout.write("  No hay datos de composición corporal")
                
                # Si hay medidas básicas pero no composición, crear composición
                if measurements.exists():
                    self.stdout.write("  Creando datos de composición corporal...")
                    latest_measurement = measurements.first()
                    
                    # Obtener género del usuario
                    user_gender = getattr(user.userprofile, 'gender', 'M') if hasattr(user, 'userprofile') else 'M'
                    
                    # Calcular IMC
                    height_m = latest_measurement.height / 100
                    imc = round(latest_measurement.weight / (height_m ** 2), 2)
                    
                    # Calcular ICA
                    ica = round(latest_measurement.waist / latest_measurement.height, 2)
                    
                    # Calcular % de grasa corporal usando fórmula US Navy
                    body_fat_percentage = self.calculate_body_fat_us_navy(
                        latest_measurement.weight, latest_measurement.height, latest_measurement.waist, 
                        latest_measurement.hip, latest_measurement.chest, latest_measurement.age, user_gender
                    )
                    
                    # Calcular masa muscular
                    muscle_mass = round(float(latest_measurement.weight) * (100 - body_fat_percentage) / 100, 1)
                    
                    # Crear registro de composición corporal
                    composition = BodyCompositionHistory.objects.create(
                        user=user,
                        measurement_date=latest_measurement.measurement_date,
                        imc=imc,
                        ica=ica,
                        body_fat_percentage=round(body_fat_percentage, 1),
                        muscle_mass=muscle_mass
                    )
                    
                    self.stdout.write(f"  ✅ Creado: IMC: {imc}, % Grasa: {body_fat_percentage:.1f}%, Músculo: {muscle_mass}kg, ICA: {ica}")

    def calculate_body_fat_us_navy(self, weight, height, waist, hip, neck, age, gender):
        """Calcula % de grasa corporal usando fórmula US Navy"""
        try:
            # Convertir Decimal a float para los cálculos
            weight = float(weight)
            height = float(height)
            waist = float(waist)
            hip = float(hip)
            neck = float(neck)
            
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
