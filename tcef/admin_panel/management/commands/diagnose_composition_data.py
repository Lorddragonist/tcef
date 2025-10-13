from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.models import UserProfile, BodyMeasurements, BodyCompositionHistory
import math


class Command(BaseCommand):
    help = 'Diagnostica problemas con datos de composición corporal (IMC, grasa, músculo)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username específico para diagnosticar (opcional)',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Intentar corregir los datos faltantes automáticamente',
        )

    def handle(self, *args, **options):
        username = options.get('user')
        fix_data = options.get('fix', False)
        
        self.stdout.write(self.style.SUCCESS('🔍 DIAGNÓSTICO DE DATOS DE COMPOSICIÓN CORPORAL'))
        self.stdout.write('=' * 60)
        
        # Obtener usuarios a diagnosticar
        if username:
            try:
                users = [User.objects.get(username=username)]
                self.stdout.write(f'Diagnosticando usuario específico: {username}')
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Usuario {username} no encontrado'))
                return
        else:
            users = User.objects.filter(userprofile__is_approved=True)
            self.stdout.write(f'Diagnosticando todos los usuarios aprobados: {users.count()}')
        
        self.stdout.write('')
        
        total_users = 0
        users_with_measurements = 0
        users_with_composition = 0
        users_with_complete_data = 0
        users_with_issues = []
        
        for user in users:
            total_users += 1
            self.stdout.write(f'👤 Usuario: {user.username}')
            
            # Verificar medidas corporales
            measurements = BodyMeasurements.objects.filter(user=user).order_by('-measurement_date')
            latest_measurement = measurements.first()
            
            if not measurements.exists():
                self.stdout.write(f'  ❌ Sin medidas corporales')
                users_with_issues.append({
                    'user': user,
                    'issue': 'Sin medidas corporales',
                    'fixable': False
                })
                continue
            
            users_with_measurements += 1
            self.stdout.write(f'  ✅ Medidas: {measurements.count()} registros')
            self.stdout.write(f'      Última: {latest_measurement.measurement_date} - Peso: {latest_measurement.weight}kg')
            
            # Verificar composición corporal
            compositions = BodyCompositionHistory.objects.filter(user=user).order_by('-measurement_date')
            latest_composition = compositions.first()
            
            if not compositions.exists():
                self.stdout.write(f'  ❌ Sin datos de composición corporal')
                users_with_issues.append({
                    'user': user,
                    'issue': 'Sin composición corporal',
                    'fixable': True,
                    'latest_measurement': latest_measurement
                })
            else:
                users_with_composition += 1
                self.stdout.write(f'  ✅ Composición: {compositions.count()} registros')
                self.stdout.write(f'      Última: {latest_composition.measurement_date}')
                self.stdout.write(f'      IMC: {latest_composition.imc}, Grasa: {latest_composition.body_fat_percentage}%, Músculo: {latest_composition.muscle_mass}kg')
            
            # Verificar datos completos
            if latest_measurement and latest_composition:
                # Verificar que los datos no sean None
                if (latest_composition.imc and latest_composition.body_fat_percentage and 
                    latest_composition.muscle_mass):
                    users_with_complete_data += 1
                    self.stdout.write(f'  ✅ Datos completos')
                else:
                    self.stdout.write(f'  ⚠️  Datos incompletos (valores None)')
                    users_with_issues.append({
                        'user': user,
                        'issue': 'Datos incompletos',
                        'fixable': True,
                        'latest_measurement': latest_measurement,
                        'latest_composition': latest_composition
                    })
            
            # Verificar datos de medidas necesarios para cálculos
            if latest_measurement:
                missing_fields = []
                if not latest_measurement.weight:
                    missing_fields.append('peso')
                if not latest_measurement.height:
                    missing_fields.append('altura')
                if not latest_measurement.waist:
                    missing_fields.append('cintura')
                if not latest_measurement.hip:
                    missing_fields.append('cadera')
                if not latest_measurement.chest:
                    missing_fields.append('pecho')
                if not latest_measurement.age:
                    missing_fields.append('edad')
                
                if missing_fields:
                    self.stdout.write(f'  ⚠️  Campos faltantes: {", ".join(missing_fields)}')
                    users_with_issues.append({
                        'user': user,
                        'issue': f'Campos faltantes: {", ".join(missing_fields)}',
                        'fixable': False
                    })
            
            self.stdout.write('')
        
        # Resumen
        self.stdout.write('📊 RESUMEN:')
        self.stdout.write(f'  Total usuarios: {total_users}')
        self.stdout.write(f'  Con medidas: {users_with_measurements}')
        self.stdout.write(f'  Con composición: {users_with_composition}')
        self.stdout.write(f'  Con datos completos: {users_with_complete_data}')
        self.stdout.write(f'  Con problemas: {len(users_with_issues)}')
        
        # Mostrar problemas encontrados
        if users_with_issues:
            self.stdout.write('')
            self.stdout.write('🚨 PROBLEMAS ENCONTRADOS:')
            for issue in users_with_issues:
                self.stdout.write(f'  • {issue["user"].username}: {issue["issue"]}')
        
        # Intentar corregir si se solicita
        if fix_data and users_with_issues:
            self.stdout.write('')
            self.stdout.write('🔧 INTENTANDO CORREGIR DATOS...')
            
            fixed_count = 0
            for issue in users_with_issues:
                if issue['fixable'] and 'latest_measurement' in issue:
                    try:
                        self.fix_user_composition_data(issue['user'], issue['latest_measurement'])
                        fixed_count += 1
                        self.stdout.write(f'  ✅ Corregido: {issue["user"].username}')
                    except Exception as e:
                        self.stdout.write(f'  ❌ Error corrigiendo {issue["user"].username}: {str(e)}')
            
            self.stdout.write(f'Corregidos: {fixed_count} usuarios')
    
    def fix_user_composition_data(self, user, measurement):
        """Intenta corregir los datos de composición corporal para un usuario"""
        from app.models import BodyCompositionHistory
        from decimal import Decimal
        
        # Obtener género del usuario
        user_gender = getattr(user.userprofile, 'gender', 'M') if hasattr(user, 'userprofile') else 'M'
        
        # Calcular métricas con validación de límites
        height_m = float(measurement.height) / 100
        imc = round(float(measurement.weight) / (height_m ** 2), 2)
        ica = round(float(measurement.waist) / float(measurement.height), 2)
        
        # Limitar valores a los rangos permitidos por la base de datos (max 999.99)
        imc = min(imc, 999.99)
        ica = min(ica, 999.99)
        
        # Calcular % de grasa corporal
        body_fat_percentage = self.calculate_body_fat_us_navy(
            measurement.weight, measurement.height, 
            measurement.waist, measurement.hip, 
            measurement.chest, measurement.age, user_gender
        )
        
        # Limitar porcentaje de grasa a 100%
        body_fat_percentage = min(body_fat_percentage, 100.0)
        
        # Calcular masa muscular
        muscle_mass = round(float(measurement.weight) * (100 - body_fat_percentage) / 100, 1)
        
        # Limitar masa muscular
        muscle_mass = min(muscle_mass, 999.99)
        
        # Debug: mostrar valores calculados
        self.stdout.write(f'    📊 Valores calculados para {user.username}:')
        self.stdout.write(f'        Peso: {measurement.weight}kg, Altura: {measurement.height}cm')
        self.stdout.write(f'        Cintura: {measurement.waist}cm, Cadera: {measurement.hip}cm, Cuello: {measurement.chest}cm')
        self.stdout.write(f'        IMC: {imc}, ICA: {ica}')
        self.stdout.write(f'        Grasa: {body_fat_percentage}%, Músculo: {muscle_mass}kg')
        
        # Validar que los valores estén dentro de rangos razonables
        if imc > 100 or ica > 10 or body_fat_percentage > 100 or muscle_mass > 500:
            raise ValueError(f"Valores fuera de rango: IMC={imc}, ICA={ica}, Grasa={body_fat_percentage}%, Músculo={muscle_mass}kg")
        
        # Crear o actualizar registro
        composition, created = BodyCompositionHistory.objects.get_or_create(
            user=user,
            measurement_date=measurement.measurement_date,
            defaults={
                'imc': imc,
                'ica': ica,
                'body_fat_percentage': round(body_fat_percentage, 1),
                'muscle_mass': muscle_mass
            }
        )
        
        if not created:
            # Actualizar registro existente
            composition.imc = imc
            composition.ica = ica
            composition.body_fat_percentage = round(body_fat_percentage, 1)
            composition.muscle_mass = muscle_mass
            composition.save()
    
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
