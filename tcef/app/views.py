from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
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
from .forms import UserRegistrationForm
from .models import UserProfile, ExerciseLog, WeeklyRoutine

def register(request):
    """Vista para el registro de usuarios"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Enviar email de confirmación
            try:
                send_confirmation_email(user)
                messages.success(
                    request, 
                    '¡Registro exitoso! Por favor, revisa tu email para confirmar tu cuenta.'
                )
                return redirect('login')
            except Exception as e:
                # Si falla el envío de email, aún creamos el usuario
                messages.warning(
                    request, 
                    'Usuario creado pero hubo un problema enviando el email de confirmación. Contacta al administrador.'
                )
                return redirect('login')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'app/register.html', {'form': form})

def confirm_email(request, token):
    """Vista para confirmar el email del usuario"""
    try:
        profile = get_object_or_404(UserProfile, email_confirmation_token=token)
        
        if profile.email_confirmed:
            messages.info(request, 'Tu email ya ha sido confirmado.')
        else:
            profile.confirm_email()
            messages.success(request, '¡Email confirmado exitosamente! Ya puedes iniciar sesión.')
        
        return redirect('login')
    
    except UserProfile.DoesNotExist:
        messages.error(request, 'El enlace de confirmación no es válido o ha expirado.')
        return redirect('login')

def send_confirmation_email(user):
    """Envía email de confirmación al usuario"""
    profile = user.userprofile
    
    # Construir la URL de confirmación
    confirmation_url = reverse('confirm_email', kwargs={'token': profile.email_confirmation_token})
    full_url = request.build_absolute_uri(confirmation_url)
    
    # Renderizar el template del email
    email_html = render_to_string('app/email/confirmation_email.html', {
        'user': user,
        'confirmation_url': full_url
    })
    
    email_text = render_to_string('app/email/confirmation_email.txt', {
        'user': user,
        'confirmation_url': full_url
    })
    
    # Enviar el email
    send_mail(
        subject='Confirma tu cuenta - TCEF',
        message=email_text,
        html_message=email_html,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

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
    
    # Obtener el calendario del mes
    cal = calendar.monthcalendar(year, month)
    
    # Obtener ejercicios del mes para el usuario
    month_exercises = ExerciseLog.get_month_exercises(request.user, year, month)
    exercise_dates = {ex.exercise_date.day: ex for ex in month_exercises}
    
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
        'calendar': cal,
        'year': year,
        'month': month,
        'month_name': month_names[month - 1],
        'exercise_dates': exercise_dates,
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

@login_required
def weekly_routines(request, day=None):
    """Vista principal de las rutinas semanales con carrusel"""
    
    # Si no se especifica día, usar el día actual
    if day is None:
        current_routine = WeeklyRoutine.get_today_routine()
        if current_routine:
            day = current_routine.day
        else:
            # Si no hay rutina para hoy, usar lunes por defecto
            day = 'lunes'
    else:
        # Validar que el día sea válido
        valid_days = [choice[0] for choice in WeeklyRoutine.DAY_CHOICES]
        if day not in valid_days:
            day = 'lunes'
    
    # Obtener la rutina del día especificado
    try:
        current_routine = WeeklyRoutine.objects.get(day=day, is_active=True)
    except WeeklyRoutine.DoesNotExist:
        current_routine = None
    
    # Obtener todas las rutinas activas para la navegación
    all_routines = WeeklyRoutine.get_all_active_routines()
    
    # Obtener información de navegación
    if current_routine:
        next_day = current_routine.get_next_day()
        previous_day = current_routine.get_previous_day()
        
        # Buscar las rutinas siguiente y anterior
        try:
            next_routine = WeeklyRoutine.objects.get(day=next_day, is_active=True)
        except WeeklyRoutine.DoesNotExist:
            next_routine = None
            
        try:
            previous_routine = WeeklyRoutine.objects.get(day=previous_day, is_active=True)
        except WeeklyRoutine.DoesNotExist:
            previous_routine = None
    else:
        next_routine = None
        previous_routine = None
    
    # Verificar si el usuario ya completó la rutina de hoy
    today = date.today()
    today_exercise = None
    if current_routine:
        try:
            today_exercise = ExerciseLog.objects.get(user=request.user, exercise_date=today)
        except ExerciseLog.DoesNotExist:
            pass
    
    context = {
        'current_routine': current_routine,
        'all_routines': all_routines,
        'next_routine': next_routine,
        'previous_routine': previous_routine,
        'current_day': day,
        'today_exercise': today_exercise,
        'today': today,
    }
    
    return render(request, 'app/weekly_routines.html', context)

@login_required
@require_POST
def complete_routine(request):
    """Vista para marcar una rutina como completada"""
    try:
        routine_day = request.POST.get('routine_day')
        
        if not routine_day:
            return JsonResponse({'success': False, 'error': 'Día de rutina requerido'})
        
        # Obtener la fecha actual
        today = date.today()
        
        # Verificar que no exista ya un ejercicio para hoy
        if ExerciseLog.objects.filter(user=request.user, exercise_date=today).exists():
            return JsonResponse({'success': False, 'error': 'Ya tienes un ejercicio registrado para hoy'})
        
        # Crear el registro de ejercicio
        exercise = ExerciseLog.objects.create(
            user=request.user,
            exercise_date=today,
            notes=f"Rutina completada: {routine_day}",
            difficulty='medio'  # Por defecto medio, se puede personalizar después
        )
        
        # Obtener estadísticas actualizadas
        user_stats = ExerciseLog.get_user_stats(request.user)
        
        return JsonResponse({
            'success': True,
            'exercise_id': exercise.id,
            'user_stats': user_stats,
            'message': '¡Rutina marcada como completada!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
