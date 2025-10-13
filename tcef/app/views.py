from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, date, timedelta
import calendar
import math  # Agregar esta importación
from .forms import UserRegistrationForm, CustomLoginForm
from .models import UserProfile, ExerciseLog, WeeklyRoutine, PasswordResetRequest
from admin_panel.models import CustomRoutine, UserGroupMembership
from .forms import BodyMeasurementsForm
from .models import BodyMeasurements
import json

def home(request):
    """Vista principal de la landing page tipo blog"""
    return render(request, 'app/home.html')

def custom_login(request):
    """Vista personalizada de login que permite username o email"""
    if request.user.is_authenticated:
        return redirect('app:profile')
    
    if request.method == 'POST':
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            # Autenticar usuario usando nuestro backend personalizado
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Configurar sesión persistente si "Recordarme" está marcado
                    if not remember_me:
                        request.session.set_expiry(0)  # Sesión se cierra al cerrar el navegador
                    
                    # Verificar si el usuario está aprobado
                    try:
                        profile = user.userprofile
                        if not profile.is_approved:
                            messages.warning(
                                request, 
                                'Tu cuenta está pendiente de aprobación por parte del administrador.'
                            )
                            logout(request)
                            return render(request, 'app/login.html', {'form': form})
                    except UserProfile.DoesNotExist:
                        # Si no existe el perfil, crear uno
                        UserProfile.objects.create(user=user)
                    
                    messages.success(request, f'¡Bienvenido, {user.first_name or user.username}!')
                    return redirect('app:profile')
                else:
                    messages.error(request, 'Tu cuenta está desactivada.')
            else:
                messages.error(request, 'Credenciales inválidas. Verifica tu nombre de usuario/email y contraseña.')
    else:
        form = CustomLoginForm()
    
    return render(request, 'app/login.html', {'form': form})

def register(request):
    """Vista para el registro de usuarios"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Crear usuario inactivo por defecto (debe ser aprobado por admin)
            user.is_active = False
            user.save()
            
            # Crear perfil de usuario
            profile = UserProfile.objects.create(user=user)
            
            # Crear solicitud de aprobación
            from admin_panel.models import UserApprovalRequest
            UserApprovalRequest.objects.create(user=user)
            
            messages.success(
                request, 
                '¡Registro exitoso! Tu cuenta está pendiente de aprobación por parte del administrador. Te notificaremos cuando sea aprobada.'
            )
            return redirect('login')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'app/register.html', {'form': form})

def request_password_reset(request):
    """Vista para solicitar reseteo de contraseña"""
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            # Verificar si ya existe una solicitud pendiente
            existing_request = PasswordResetRequest.objects.filter(
                user=user, 
                status='pending'
            ).first()
            
            if existing_request:
                messages.info(request, 'Ya tienes una solicitud de reseteo pendiente. El administrador la revisará pronto.')
            else:
                # Crear nueva solicitud
                reset_request = PasswordResetRequest.objects.create(user=user)
                
                # Crear solicitud de aprobación
                from admin_panel.models import PasswordResetApproval
                PasswordResetApproval.objects.create(reset_request=reset_request)
                
                messages.success(request, 'Solicitud de reseteo enviada. El administrador la revisará y te notificará.')
            
            return redirect('login')
            
        except User.DoesNotExist:
            messages.error(request, 'No se encontró un usuario con ese email.')
    
    return render(request, 'app/request_password_reset.html')

def reset_password_with_token(request, token):
    """Vista para cambiar contraseña usando el token aprobado por admin"""
    try:
        reset_request = get_object_or_404(PasswordResetRequest, reset_token=token)
        
        if not reset_request.is_token_valid():
            messages.error(request, 'El enlace de reseteo no es válido o ha expirado.')
            return redirect('login')
        
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            if password1 == password2:
                user = reset_request.user
                user.set_password(password1)
                user.save()
                
                # Marcar el reseteo como completado
                reset_request.complete_reset()
                
                messages.success(request, 'Contraseña cambiada exitosamente. Ya puedes iniciar sesión.')
                return redirect('login')
            else:
                messages.error(request, 'Las contraseñas no coinciden.')
        
        return render(request, 'app/reset_password.html', {'token': token})
        
    except PasswordResetRequest.DoesNotExist:
        messages.error(request, 'El enlace de reseteo no es válido.')
        return redirect('login')

@login_required
def profile(request):
    """Vista del perfil del usuario"""
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    # Obtener estadísticas básicas
    exercise_stats = ExerciseLog.get_user_stats(request.user)
    
    context = {
        'profile': profile,
        'user': request.user,
        'exercise_stats': exercise_stats
    }
    return render(request, 'app/profile.html', context)

@login_required
def exercise_calendar(request, year=None, month=None):
    """Vista principal del calendario de ejercicios"""
    # Obtener año y mes actuales si no se especifican
    if year is None or month is None:
        today = date.today()
        year = today.year
        month = today.month
    
    # Validar año y mes
    try:
        year = int(year)
        month = int(month)
        if month < 1 or month > 12:
            raise ValueError("Mes inválido")
    except (ValueError, TypeError):
        today = date.today()
        year = today.year
        month = today.month
    
    # Obtener el primer día del mes
    first_day = date(year, month, 1)
    
    # Obtener el lunes de la semana que contiene el primer día del mes
    days_since_monday = first_day.weekday()
    calendar_start = first_day - timedelta(days=days_since_monday)
    
    # Obtener el último día del mes
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    # Obtener el domingo de la semana que contiene el último día del mes
    days_until_sunday = 6 - last_day.weekday()
    calendar_end = last_day + timedelta(days=days_until_sunday)
    
    # Crear el calendario extendido semana por semana
    extended_calendar = []
    current_date = calendar_start
    
    while current_date <= calendar_end:
        week = []
        for i in range(7):  # 7 días por semana (Lunes a Domingo)
            day_info = {
                'day': current_date.day,
                'month': current_date.month,
                'year': current_date.year,
                'is_current_month': current_date.month == month and current_date.year == year,
                'is_today': current_date == date.today(),
                'date': current_date,
            }
            week.append(day_info)
            current_date += timedelta(days=1)
        extended_calendar.append(week)
    
    # Obtener ejercicios del rango extendido para el usuario
    extended_exercises = ExerciseLog.objects.filter(
        user=request.user,
        exercise_date__gte=calendar_start,
        exercise_date__lte=calendar_end
    )
    exercise_dates = {ex.exercise_date: ex for ex in extended_exercises}
    
    # Obtener rutinas asignadas para el rango del calendario
    assigned_routines = {}
    try:
        user_membership = request.user.group_membership
        user_group = user_membership.group
        group_routines = CustomRoutine.objects.filter(
            group=user_group,
            is_active=True,
            assigned_date__gte=calendar_start,
            assigned_date__lte=calendar_end
        ).prefetch_related('routine_videos__video')
        
        for routine in group_routines:
            videos_data = []
            for rv in routine.get_videos_ordered():
                videos_data.append({
                    'id': rv.video.id,
                    'title': rv.video.title,
                    'description': rv.video.description,
                    'duration': rv.video.get_duration_formatted(),
                    's3_url': rv.video.s3_url,
                    'thumbnail_url': rv.video.thumbnail_url,
                    'order': rv.order,
                    'notes': rv.notes
                })
            
            assigned_routines[routine.assigned_date] = {
                'id': routine.id,
                'title': routine.title,
                'description': routine.description,
                'videos_count': routine.get_videos_count(),
                'total_duration': routine.get_total_duration(),
                'videos': videos_data
            }
    except UserGroupMembership.DoesNotExist:
        # Usuario no está en ningún grupo
        pass
    
    # Obtener estadísticas del usuario
    user_stats = ExerciseLog.get_user_stats(request.user)
    
    # Calcular navegación de meses
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year
    
    # Nombres de los meses
    month_names = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    
    context = {
        'calendar': extended_calendar,
        'year': year,
        'month': month,
        'month_name': month_names[month - 1],
        'exercise_dates': exercise_dates,
        'assigned_routines': assigned_routines,  # Nueva variable para rutinas asignadas
        'user_stats': user_stats,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': date.today(),
    }
    
    return render(request, 'app/exercise_calendar.html', context)

@login_required
@require_POST
def add_exercise(request):
    """Vista para agregar un ejercicio completado"""
    try:
        exercise_date = request.POST.get('exercise_date')
        notes = request.POST.get('notes', '')
        difficulty = request.POST.get('difficulty', 'medio')
        
        if not exercise_date:
            return JsonResponse({'success': False, 'error': 'Fecha requerida'})
        
        # Convertir fecha string a objeto date
        exercise_date = datetime.strptime(exercise_date, '%Y-%m-%d').date()
        
        # Verificar que no exista ya un ejercicio para esa fecha
        if ExerciseLog.objects.filter(user=request.user, exercise_date=exercise_date).exists():
            return JsonResponse({'success': False, 'error': 'Ya tienes un ejercicio registrado para esta fecha'})
        
        # Crear el registro de ejercicio
        exercise = ExerciseLog.objects.create(
            user=request.user,
            exercise_date=exercise_date,
            notes=notes,
            difficulty=difficulty
        )
        
        # Obtener estadísticas actualizadas
        user_stats = ExerciseLog.get_user_stats(request.user)
        
        return JsonResponse({
            'success': True,
            'exercise_id': exercise.id,
            'difficulty': exercise.get_difficulty_display(),
            'user_stats': user_stats
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def remove_exercise(request):
    """Vista para remover un ejercicio completado"""
    try:
        exercise_date = request.POST.get('exercise_date')
        
        if not exercise_date:
            return JsonResponse({'success': False, 'error': 'Fecha requerida'})
        
        # Convertir fecha string a objeto date
        exercise_date = datetime.strptime(exercise_date, '%Y-%m-%d').date()
        
        # Buscar y eliminar el ejercicio
        exercise = get_object_or_404(ExerciseLog, user=request.user, exercise_date=exercise_date)
        exercise.delete()
        
        # Obtener estadísticas actualizadas
        user_stats = ExerciseLog.get_user_stats(request.user)
        
        return JsonResponse({
            'success': True,
            'user_stats': user_stats
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def exercise_stats(request):
    # Obtener las medidas del usuario
    measurements = BodyMeasurements.objects.filter(user=request.user).order_by('measurement_date')
    
    # Preparar datos para el gráfico con todas las métricas
    measurements_data = {
        'labels': [m.measurement_date.strftime('%Y-%m-%d') for m in measurements],
        'weights': [float(m.weight) for m in measurements],
        'waists': [float(m.waist) for m in measurements],
        'hips': [float(m.hip) for m in measurements],
        'imcs': [],
        'icas': [],
        'body_fat_percentages': [],
        'muscle_masses': [],
    }
    
    # Obtener el género del usuario
    try:
        user_gender = request.user.userprofile.gender
    except:
        user_gender = 'F'  # Por defecto usar fórmula de mujer si no tiene género
    
    # Calcular métricas para cada medición
    for m in measurements:
        weight_kg = float(m.weight)
        height_cm = float(m.height)
        waist_cm = float(m.waist)
        hip_cm = float(m.hip)
        neck_cm = float(m.chest)  # El campo chest representa el cuello
        age_years = m.age
        
        # Calcular IMC
        if height_cm > 0:
            height_m = height_cm / 100
            imc = round(weight_kg / (height_m ** 2), 1)
        else:
            imc = 0
        measurements_data['imcs'].append(imc)
        
        # Calcular ICA
        if height_cm > 0:
            ica = round(waist_cm / height_cm, 2)
        else:
            ica = 0
        measurements_data['icas'].append(ica)
        
        # Calcular % de Grasa Corporal usando fórmula US Navy CORRECTA
        if height_cm > 0 and waist_cm > 0 and neck_cm > 0:
            try:
                if user_gender == 'M':  # Hombre
                    # Fórmula US Navy para hombres: 495 / (1.0324 - 0.19077 * log(cintura - cuello) + 0.15456 * log(altura)) - 450
                    if waist_cm > neck_cm:  # Verificar que cintura > cuello
                        body_fat_percentage = 495 / (1.0324 - 0.19077 * math.log10(waist_cm - neck_cm) + 0.15456 * math.log10(height_cm)) - 450
                    else:
                        body_fat_percentage = 0
                else:  # Mujer (o por defecto)
                    # Fórmula US Navy para mujeres: 495 / (1.29579 - 0.35004 * log(cintura + cadera - cuello) + 0.22100 * log(altura)) - 450
                    if (waist_cm + hip_cm) > neck_cm:  # Verificar que (cintura + cadera) > cuello
                        body_fat_percentage = 495 / (1.29579 - 0.35004 * math.log10(waist_cm + hip_cm - neck_cm) + 0.22100 * math.log10(height_cm)) - 450
                    else:
                        body_fat_percentage = 0
                
                # Limitar el resultado entre 0-100%
                body_fat_percentage = round(max(0, min(100, body_fat_percentage)), 1)
            except (ValueError, ZeroDivisionError):
                # En caso de error en el cálculo (logaritmo de número negativo o división por cero)
                body_fat_percentage = 0
        else:
            body_fat_percentage = 0
        measurements_data['body_fat_percentages'].append(body_fat_percentage)
        
        # Calcular Masa Muscular (Masa corporal magra)
        if height_cm > 0 and age_years > 0 and body_fat_percentage > 0:
            # Masa corporal magra = Peso × (100 - %grasa corporal) / 100
            muscle_mass = round(weight_kg * (100 - body_fat_percentage) / 100, 1)
        else:
            muscle_mass = 0
        measurements_data['muscle_masses'].append(muscle_mass)
    
    # Obtener las últimas medidas corporales
    last_measurement = BodyMeasurements.objects.filter(user=request.user).order_by('-measurement_date').first()
    
    # Inicializar valores por defecto
    imc = "--"
    ica = "--"
    body_fat_percentage = "--"
    muscle_mass = "--"
    last_measurement_date = "--"
    
    if last_measurement:
        last_measurement_date = last_measurement.measurement_date.strftime('%Y-%m-%d')
        weight_kg = float(last_measurement.weight)
        height_cm = float(last_measurement.height)
        waist_cm = float(last_measurement.waist)
        hip_cm = float(last_measurement.hip)
        neck_cm = float(last_measurement.chest)
        age_years = last_measurement.age
        
        # Calcular IMC (Índice de Masa Corporal)
        if height_cm > 0:
            height_m = height_cm / 100  # Convertir cm a metros
            imc = round(weight_kg / (height_m ** 2), 1)
        
        # Calcular ICA (Índice de Cintura-Altura)
        if height_cm > 0:
            ica = round(waist_cm / height_cm, 2)
        
        # Calcular % de Grasa Corporal usando fórmula US Navy CORRECTA
        if height_cm > 0 and waist_cm > 0 and neck_cm > 0:
            try:
                if user_gender == 'M':  # Hombre
                    # Fórmula US Navy para hombres: 495 / (1.0324 - 0.19077 * log(cintura - cuello) + 0.15456 * log(altura)) - 450
                    if waist_cm > neck_cm:  # Verificar que cintura > cuello
                        body_fat_percentage = 495 / (1.0324 - 0.19077 * math.log10(waist_cm - neck_cm) + 0.15456 * math.log10(height_cm)) - 450
                    else:
                        body_fat_percentage = 0
                else:  # Mujer (o por defecto)
                    # Fórmula US Navy para mujeres: 495 / (1.29579 - 0.35004 * log(cintura + cadera - cuello) + 0.22100 * log(altura)) - 450
                    if (waist_cm + hip_cm) > neck_cm:  # Verificar que (cintura + cadera) > cuello
                        body_fat_percentage = 495 / (1.29579 - 0.35004 * math.log10(waist_cm + hip_cm - neck_cm) + 0.22100 * math.log10(height_cm)) - 450
                    else:
                        body_fat_percentage = 0
                
                # Limitar el resultado entre 0-100%
                body_fat_percentage = round(max(0, min(100, body_fat_percentage)), 1)
            except (ValueError, ZeroDivisionError):
                # En caso de error en el cálculo
                body_fat_percentage = 0
        
        # Calcular Masa Muscular (Masa corporal magra)
        if height_cm > 0 and age_years > 0 and body_fat_percentage > 0:
            # Masa corporal magra = Peso × (100 - %grasa corporal) / 100
            muscle_mass = round(weight_kg * (100 - body_fat_percentage) / 100, 1)
    
    # Obtener datos de ejercicios para rachas
    exercises = ExerciseLog.objects.filter(user=request.user).order_by('exercise_date')
    
    # Calcular rachas
    current_streak = ExerciseLog.get_current_week_streak(request.user)
    longest_streak = ExerciseLog.get_longest_week_streak(request.user)
    
    # Calcular progreso semanal
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    current_week_exercises = ExerciseLog.objects.filter(
        user=request.user,
        exercise_date__gte=week_start,
        exercise_date__lte=week_end
    ).count()
    
    weekly_progress = min((current_week_exercises / 5) * 100, 100)
    
    # Calcular distribución por dificultad del mes actual
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    difficulty_data = {
        'facil': ExerciseLog.objects.filter(
            user=request.user,
            exercise_date__year=current_year,
            exercise_date__month=current_month,
            difficulty='facil'
        ).count(),
        'medio': ExerciseLog.objects.filter(
            user=request.user,
            exercise_date__year=current_year,
            exercise_date__month=current_month,
            difficulty='medio'
        ).count(),
        'dificil': ExerciseLog.objects.filter(
            user=request.user,
            exercise_date__year=current_year,
            exercise_date__month=current_month,
            difficulty='dificil'
        ).count(),
    }
    
    # Calcular progreso mensual
    total_exercises_this_month = ExerciseLog.objects.filter(
        user=request.user,
        exercise_date__year=current_year,
        exercise_date__month=current_month
    ).count()

    # Calcular días laborables del mes (lunes a viernes)
    month_days = calendar.monthrange(current_year, current_month)[1]
    weekdays_in_month = 0
    for day in range(1, month_days + 1):
        if calendar.weekday(current_year, current_month, day) < 5:  # 0-4 = lunes a viernes
            weekdays_in_month += 1

    # Progreso mensual basado en días laborables
    progress_percentage = min((total_exercises_this_month / weekdays_in_month) * 100, 100) if weekdays_in_month > 0 else 0

    user_stats = {
        'total_exercises': ExerciseLog.objects.filter(user=request.user).count(),
        'current_streak': current_streak,
        'longest_streak': longest_streak,
        'weekly_progress': weekly_progress,
        'current_week_exercises': current_week_exercises,
        'total_exercises_this_month': total_exercises_this_month,  # Agregar esta línea
        'progress_percentage': progress_percentage,  # Agregar esta línea
        'imc': imc,
        'ica': ica,
        'body_fat_percentage': body_fat_percentage,
        'muscle_mass': muscle_mass,
        'last_measurement_date': last_measurement_date,
    }
    
    context = {
        'user_stats': user_stats,
        'measurements_data_json': json.dumps(measurements_data),
        'difficulty_data': difficulty_data,
    }
    return render(request, 'app/exercise_stats.html', context)

def custom_logout(request):
    """Vista personalizada de logout con confirmación"""
    if request.method == 'POST':
        # Confirmar logout
        logout(request)
        messages.success(request, '¡Has cerrado sesión exitosamente! Gracias por usar TCEF.')
        return redirect('login')
    
    # Mostrar página de confirmación
    return render(request, 'app/logout.html')

def custom_404(request, exception=None):
    """Vista personalizada para error 404"""
    return render(request, 'app/404.html', status=404)

def under_construction(request):
    """Vista para páginas en construcción"""
    return render(request, 'app/under_construction.html')

def test_404(request):
    """Vista de prueba para la página 404"""
    return render(request, 'app/404.html', status=404)

@login_required
def add_body_measurements(request):
    if request.method == 'POST':
        form = BodyMeasurementsForm(request.POST)
        if form.is_valid():
            measurement = form.save(commit=False)
            measurement.user = request.user
            
            # Verificar si ya existe un registro para esta fecha
            existing_measurement = BodyMeasurements.objects.filter(
                user=request.user,
                measurement_date=measurement.measurement_date
            ).first()
            
            if existing_measurement:
                # Actualizar el registro existente
                existing_measurement.weight = measurement.weight
                existing_measurement.height = measurement.height
                existing_measurement.age = measurement.age
                existing_measurement.waist = measurement.waist
                existing_measurement.hip = measurement.hip
                existing_measurement.chest = measurement.chest
                existing_measurement.save()
                measurement = existing_measurement
                messages.success(request, 'Medidas actualizadas correctamente!')
            else:
                # Crear nuevo registro
                measurement.save()
                messages.success(request, 'Medidas registradas correctamente!')
            
            # Crear o actualizar registro de composición corporal
            from .models import BodyCompositionHistory
            import math
            
            # Obtener género del usuario
            user_gender = getattr(request.user.userprofile, 'gender', 'M') if hasattr(request.user, 'userprofile') else 'M'
            
            # Calcular IMC
            height_m = float(measurement.height) / 100
            imc = round(float(measurement.weight) / (height_m ** 2), 2)
            
            # Calcular ICA (Índice Cintura-Altura)
            ica = round(float(measurement.waist) / float(measurement.height), 2)
            
            # Calcular % de grasa corporal usando fórmula US Navy
            try:
                body_fat_percentage = calculate_body_fat_us_navy(
                    float(measurement.weight), float(measurement.height), float(measurement.waist), 
                    float(measurement.hip), float(measurement.chest), int(measurement.age), user_gender
                )
            except (ValueError, ZeroDivisionError, TypeError):
                body_fat_percentage = 0
                messages.warning(request, 'No se pudo calcular el porcentaje de grasa corporal con los datos proporcionados.')
            
            # Calcular masa muscular
            try:
                # Convertir Decimal a float para el cálculo
                weight_float = float(measurement.weight)
                muscle_mass = round(weight_float * (100 - body_fat_percentage) / 100, 1)
            except (ValueError, ZeroDivisionError, TypeError):
                muscle_mass = 0
                messages.warning(request, 'No se pudo calcular la masa muscular.')
            
            # Crear o actualizar registro de composición corporal
            composition, created = BodyCompositionHistory.objects.get_or_create(
                user=request.user,
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
            
            return redirect('app:exercise_stats')
        else:
            # Si el formulario no es válido, mostrar errores
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        # Obtener las últimas medidas del usuario
        last_measurement = BodyMeasurements.objects.filter(
            user=request.user
        ).order_by('-measurement_date').first()
        
        # Preparar datos iniciales
        initial_data = {
            'measurement_date': timezone.now().date()
        }
        
        # Si hay medidas anteriores, usarlas como valores por defecto
        if last_measurement:
            initial_data.update({
                'weight': last_measurement.weight,
                'height': last_measurement.height,
                'age': last_measurement.age,
                'waist': last_measurement.waist,
                'hip': last_measurement.hip,
                'chest': last_measurement.chest,
            })
        
        form = BodyMeasurementsForm(initial=initial_data)
    
    return render(request, 'app/add_measurements.html', {'form': form})

# Función corregida con las fórmulas exactas de tu fisioterapeuta
def calculate_body_fat_us_navy(weight, height, waist, hip, neck, age, gender):
    """
    Calcula % de grasa corporal usando fórmula US Navy (según fisioterapeuta)
    """
    try:
        if gender == 'M':  # Hombre
            if waist <= neck:
                return 0  # Medidas inválidas
            # Fórmula para hombres: 495 / (1.0324 - 0.19077 * log(cintura - cuello) + 0.15456 * log(altura)) - 450
            body_fat = 495 / (1.0324 - 0.19077 * math.log10(waist - neck) + 0.15456 * math.log10(height)) - 450
        else:  # Mujer
            if (waist + hip) <= neck:
                return 0  # Medidas inválidas
            # Fórmula para mujeres: 495 / (1.29579 - 0.35004 * log(cintura + cadera - cuello) + 0.22100 * log(altura)) - 450
            body_fat = 495 / (1.29579 - 0.35004 * math.log10(waist + hip - neck) + 0.22100 * math.log10(height)) - 450
        
        # Limitar resultado entre 0-100%
        return max(0, min(100, body_fat))
    
    except (ValueError, ZeroDivisionError):
        return 0

# Probar con tus medidas
result = calculate_body_fat_us_navy(105, 176, 107, 111, 44, 30, 'M')
print(f"Resultado con fórmula correcta: {result:.1f}%")

# Probar la nueva fórmula de masa muscular
print("=== NUEVA FÓRMULA DE MASA MUSCULAR ===")

# Tus medidas
weight_kg = 105
body_fat_percentage = 25.0  # Ejemplo: 25% de grasa corporal

# Fórmula anterior (aproximada)
old_muscle_mass = weight_kg * 0.4 + (176 - 100) * 0.1
print(f"Fórmula anterior: {old_muscle_mass:.1f} kg")

# Nueva fórmula (más precisa)
new_muscle_mass = weight_kg * (100 - body_fat_percentage) / 100
print(f"Nueva fórmula: {new_muscle_mass:.1f} kg")

print(f"\nDiferencia: {new_muscle_mass - old_muscle_mass:.1f} kg")