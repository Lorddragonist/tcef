from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
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
from .forms import UserRegistrationForm, CustomLoginForm
from .models import UserProfile, ExerciseLog, WeeklyRoutine, PasswordResetRequest
from admin_panel.models import CustomRoutine, UserGroupMembership

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
    """Vista para mostrar estadísticas detalladas del usuario"""
    user_stats = ExerciseLog.get_user_stats(request.user)
    
    # Obtener ejercicios de los últimos 30 días
    thirty_days_ago = date.today() - timedelta(days=30)
    recent_exercises = ExerciseLog.objects.filter(
        user=request.user,
        exercise_date__gte=thirty_days_ago
    ).order_by('-exercise_date')
    
    # Obtener distribución por dificultad
    difficulty_stats = {}
    for difficulty in ExerciseLog.DIFFICULTY_CHOICES:
        count = ExerciseLog.objects.filter(
            user=request.user,
            difficulty=difficulty[0]
        ).count()
        difficulty_stats[difficulty[1]] = count
    
    context = {
        'user_stats': user_stats,
        'recent_exercises': recent_exercises,
        'difficulty_stats': difficulty_stats,
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
