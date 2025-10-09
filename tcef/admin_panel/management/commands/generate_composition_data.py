from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.models import BodyMeasurements, BodyCompositionHistory
import math

class Command(BaseCommand):
    help = 'Generate body composition data for users with basic measurements but no composition data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Buscar usuarios con medidas básicas pero sin composición corporal
        users_with_measurements = User.objects.filter(
            body_measurements__isnull=False
        ).distinct()
        
        users_to_process = []
        
        for user in users_with_measurements:
            has_composition = BodyCompositionHistory.objects.filter(user=user).exists()
            if not has_composition:
                users_to_process.append(user)
        
        count = len(users_to_process)
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Todos los usuarios con medidas básicas ya tienen datos de composición corporal.')
            )
            return
        
        self.stdout.write(f'📊 Encontrados {count} usuarios con medidas básicas pero sin composición corporal')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 MODO DRY-RUN - No se crearán registros')
            )
        
        created_count = 0
        
        for user in users_to_process:
            try:
                # Obtener la medida más reciente
                latest_measurement = BodyMeasurements.objects.filter(
                    user=user
                ).order_by('-measurement_date').first()
                
                if not latest_measurement:
                    continue
                
                # Obtener género del usuario
                user_gender = getattr(user.userprofile, 'gender', 'M') if hasattr(user, 'userprofile') else 'M'
                
                # Calcular métricas
                height_m = latest_measurement.height / 100
                imc = round(latest_measurement.weight / (height_m ** 2), 2)
                ica = round(latest_measurement.waist / latest_measurement.height, 2)
                
                # Calcular % de grasa corporal
                body_fat_percentage = self.calculate_body_fat_us_navy(
                    latest_measurement.weight, latest_measurement.height, 
                    latest_measurement.waist, latest_measurement.hip, 
                    latest_measurement.chest, latest_measurement.age, user_gender
                )
                
                # Calcular masa muscular
                muscle_mass = round(float(latest_measurement.weight) * (100 - body_fat_percentage) / 100, 1)
                
                if dry_run:
                    self.stdout.write(
                        f'  🔍 Se crearía para {user.username}:'
                    )
                    self.stdout.write(f'    - Fecha: {latest_measurement.measurement_date}')
                    self.stdout.write(f'    - IMC: {imc}')
                    self.stdout.write(f'    - ICA: {ica}')
                    self.stdout.write(f'    - % Grasa: {body_fat_percentage:.1f}%')
                    self.stdout.write(f'    - Masa Muscular: {muscle_mass}kg')
                else:
                    # Crear composición corporal
                    composition = BodyCompositionHistory.objects.create(
                        user=user,
                        measurement_date=latest_measurement.measurement_date,
                        imc=imc,
                        ica=ica,
                        body_fat_percentage=round(body_fat_percentage, 1),
                        muscle_mass=muscle_mass
                    )
                    
                    self.stdout.write(
                        f'  ✅ Creado para {user.username}:'
                    )
                    self.stdout.write(f'    - % Grasa: {body_fat_percentage:.1f}%')
                    self.stdout.write(f'    - Masa Muscular: {muscle_mass}kg')
                    self.stdout.write(f'    - ICA: {ica}')
                
                created_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error procesando {user.username}: {str(e)}')
                )
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Proceso completado. {created_count} registros de composición corporal creados.')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'🔍 DRY-RUN completado. {created_count} registros serían creados.')
            )
            self.stdout.write(
                self.style.WARNING('Para crear los registros, ejecuta el comando sin --dry-run')
            )
    
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
