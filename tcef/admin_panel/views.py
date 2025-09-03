from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime, timedelta

from .models import UserGroup, UserGroupMembership, CustomRoutine, AdminActivity, VideoUploadSession
from app.models import UserProfile, ExerciseLog

import boto3
from botocore.exceptions import ClientError
from django.conf import settings


def is_staff_user(user):
    """Verifica si el usuario es staff"""
    return user.is_authenticated and user.is_staff


@user_passes_test(is_staff_user, login_url='/login/')
def admin_dashboard(request):
    """Dashboard principal del panel de administración"""
    # Estadísticas generales
    total_users = User.objects.count()
    active_users = UserProfile.objects.filter(is_approved=True).count()
    total_groups = UserGroup.objects.filter(is_active=True).count()
    total_routines = CustomRoutine.objects.filter(is_active=True).count()
    
    # Actividad reciente
    recent_activities = AdminActivity.objects.select_related('admin_user')[:10]
    
    # Usuarios recientes
    recent_users = User.objects.select_related('userprofile').order_by('-date_joined')[:5]
    
    # Rutinas de hoy
    today_routines = CustomRoutine.objects.filter(
        assigned_date=timezone.now().date(),
        is_active=True
    ).select_related('group')
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'total_groups': total_groups,
        'total_routines': total_routines,
        'recent_activities': recent_activities,
        'recent_users': recent_users,
        'today_routines': today_routines,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def user_management(request):
    """Gestión de usuarios"""
    search_query = request.GET.get('search', '')
    group_filter = request.GET.get('group', '')
    status_filter = request.GET.get('status', '')
    
    users = User.objects.select_related('userprofile').prefetch_related('group_memberships__group')
    
    # Filtros
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if group_filter:
        users = users.filter(group_memberships__group_id=group_filter)
    
    if status_filter == 'active':
        users = users.filter(userprofile__is_approved=True)
    elif status_filter == 'inactive':
        users = users.filter(userprofile__is_approved=False)
    
    # Paginación
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'groups': groups,
        'search_query': search_query,
        'group_filter': group_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'admin_panel/user_management.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def create_user(request):
    """Crear usuario desde el panel admin"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.save()
            
            # Crear perfil de usuario
            profile = UserProfile.objects.create(
                user=user,
                is_approved=True,  # Los usuarios creados por admin están aprobados
                terms_accepted=True,
                terms_accepted_date=timezone.now()
            )
            
            # Asignar grupos si se especificaron
            group_ids = request.POST.getlist('groups')
            for group_id in group_ids:
                if group_id:
                    group = UserGroup.objects.get(id=group_id)
                    UserGroupMembership.objects.create(user=user, group=group)
            
            # Registrar actividad
            AdminActivity.objects.create(
                admin_user=request.user,
                action='user_created',
                target_model='User',
                target_id=user.id,
                details=f'Usuario creado: {user.username}'
            )
            
            messages.success(request, f'Usuario {user.username} creado exitosamente.')
            return redirect('admin_panel:user_management')
    else:
        form = UserCreationForm()
    
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'form': form,
        'groups': groups,
    }
    
    return render(request, 'admin_panel/create_user.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def edit_user(request, user_id):
    """Editar usuario"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # Actualizar campos básicos
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.is_active = request.POST.get('is_active') == 'on'
        user.save()
        
        # Actualizar perfil
        profile = user.userprofile
        profile.is_approved = request.POST.get('is_approved') == 'on'
        profile.save()
        
        # Actualizar grupos
        UserGroupMembership.objects.filter(user=user).delete()
        group_ids = request.POST.getlist('groups')
        for group_id in group_ids:
            if group_id:
                group = UserGroup.objects.get(id=group_id)
                UserGroupMembership.objects.create(user=user, group=group)
        
        # Registrar actividad
        AdminActivity.objects.create(
            admin_user=request.user,
            action='user_updated',
            target_model='User',
            target_id=user.id,
            details=f'Usuario actualizado: {user.username}'
        )
        
        messages.success(request, f'Usuario {user.username} actualizado exitosamente.')
        return redirect('admin_panel:user_management')
    
    user_groups = [membership.group.id for membership in user.group_memberships.all()]
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'user': user,
        'groups': groups,
        'user_groups': user_groups,
    }
    
    return render(request, 'admin_panel/edit_user.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def delete_user(request, user_id):
    """Eliminar usuario"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        
        # Registrar actividad
        AdminActivity.objects.create(
            admin_user=request.user,
            action='user_deleted',
            target_model='User',
            target_id=user_id,
            details=f'Usuario eliminado: {username}'
        )
        
        messages.success(request, f'Usuario {username} eliminado exitosamente.')
        return redirect('admin_panel:user_management')
    
    context = {
        'user': user,
    }
    
    return render(request, 'admin_panel/delete_user.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def group_management(request):
    """Gestión de grupos de usuarios"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            name = request.POST.get('name')
            description = request.POST.get('description')
            color = request.POST.get('color', '#007bff')
            
            group = UserGroup.objects.create(
                name=name,
                description=description,
                color=color
            )
            
            AdminActivity.objects.create(
                admin_user=request.user,
                action='group_created',
                target_model='UserGroup',
                target_id=group.id,
                details=f'Grupo creado: {group.name}'
            )
            
            messages.success(request, f'Grupo {group.name} creado exitosamente.')
            
        elif action == 'update':
            group_id = request.POST.get('group_id')
            group = get_object_or_404(UserGroup, id=group_id)
            
            group.name = request.POST.get('name')
            group.description = request.POST.get('description')
            group.color = request.POST.get('color')
            group.is_active = request.POST.get('is_active') == 'on'
            group.save()
            
            AdminActivity.objects.create(
                admin_user=request.user,
                action='group_updated',
                target_model='UserGroup',
                target_id=group.id,
                details=f'Grupo actualizado: {group.name}'
            )
            
            messages.success(request, f'Grupo {group.name} actualizado exitosamente.')
            
        elif action == 'delete':
            group_id = request.POST.get('group_id')
            group = get_object_or_404(UserGroup, id=group_id)
            
            group_name = group.name
            group.delete()
            
            AdminActivity.objects.create(
                admin_user=request.user,
                action='group_deleted',
                target_model='UserGroup',
                target_id=group_id,
                details=f'Grupo eliminado: {group_name}'
            )
            
            messages.success(request, f'Grupo {group_name} eliminado exitosamente.')
    
    groups = UserGroup.objects.all().order_by('name')
    
    context = {
        'groups': groups,
    }
    
    return render(request, 'admin_panel/group_management.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def routine_management(request):
    """Gestión de rutinas personalizadas"""
    search_query = request.GET.get('search', '')
    group_filter = request.GET.get('group', '')
    date_filter = request.GET.get('date', '')
    
    routines = CustomRoutine.objects.select_related('group', 'created_by')
    
    # Filtros
    if search_query:
        routines = routines.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if group_filter:
        routines = routines.filter(group_id=group_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            routines = routines.filter(assigned_date=filter_date)
        except ValueError:
            pass
    
    # Paginación
    paginator = Paginator(routines, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'groups': groups,
        'search_query': search_query,
        'group_filter': group_filter,
        'date_filter': date_filter,
    }
    
    return render(request, 'admin_panel/routine_management.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def create_routine(request):
    """Crear nueva rutina personalizada"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        video_url = request.POST.get('video_url')
        thumbnail_url = request.POST.get('thumbnail_url', '')
        duration = request.POST.get('duration')
        group_id = request.POST.get('group')
        assigned_date = request.POST.get('assigned_date')
        
        try:
            group = UserGroup.objects.get(id=group_id)
            duration = int(duration)
            
            routine = CustomRoutine.objects.create(
                title=title,
                description=description,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                duration=duration,
                group=group,
                assigned_date=assigned_date,
                created_by=request.user
            )
            
            AdminActivity.objects.create(
                admin_user=request.user,
                action='routine_created',
                target_model='CustomRoutine',
                target_id=routine.id,
                details=f'Rutina creada: {routine.title}'
            )
            
            messages.success(request, f'Rutina {routine.title} creada exitosamente.')
            return redirect('admin_panel:routine_management')
            
        except (ValueError, UserGroup.DoesNotExist):
            messages.error(request, 'Error al crear la rutina. Verifica los datos.')
    
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'groups': groups,
    }
    
    return render(request, 'admin_panel/create_routine.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def edit_routine(request, routine_id):
    """Editar rutina existente"""
    routine = get_object_or_404(CustomRoutine, id=routine_id)
    
    if request.method == 'POST':
        routine.title = request.POST.get('title')
        routine.description = request.POST.get('description')
        routine.video_url = request.POST.get('video_url')
        routine.thumbnail_url = request.POST.get('thumbnail_url', '')
        routine.duration = int(request.POST.get('duration'))
        routine.group_id = request.POST.get('group')
        routine.assigned_date = request.POST.get('assigned_date')
        routine.is_active = request.POST.get('is_active') == 'on'
        routine.save()
        
        AdminActivity.objects.create(
            admin_user=request.user,
            action='routine_updated',
            target_model='CustomRoutine',
            target_id=routine.id,
            details=f'Rutina actualizada: {routine.title}'
        )
        
        messages.success(request, f'Rutina {routine.title} actualizada exitosamente.')
        return redirect('admin_panel:routine_management')
    
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'routine': routine,
        'groups': groups,
    }
    
    return render(request, 'admin_panel/edit_routine.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def delete_routine(request, routine_id):
    """Eliminar rutina"""
    routine = get_object_or_404(CustomRoutine, id=routine_id)
    
    if request.method == 'POST':
        routine_title = routine.title
        routine.delete()
        
        AdminActivity.objects.create(
            admin_user=request.user,
            action='routine_deleted',
            target_model='CustomRoutine',
            target_id=routine_id,
            details=f'Rutina eliminada: {routine_title}'
        )
        
        messages.success(request, f'Rutina {routine_title} eliminada exitosamente.')
        return redirect('admin_panel:routine_management')
    
    context = {
        'routine': routine,
    }
    
    return render(request, 'admin_panel/delete_routine.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def video_upload(request):
    """Página para subir videos a GCP"""
    if request.method == 'POST':
        # Obtener archivo del request
        video_file = request.FILES.get('video')
        
        if video_file:
            # Crear sesión
            upload_session = VideoUploadSession.objects.create(
                admin_user=request.user,
                filename=video_file.name,
                file_size=video_file.size,
                s3_bucket=settings.AWS_STORAGE_BUCKET_NAME,  # Bucket desde settings
                status='uploading'
            )
            
            try:
                # Subir a S3
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME
                )
                
                s3_key = f"videos/{upload_session.id}/{video_file.name}"
                
                s3_client.upload_fileobj(
                    video_file,
                    settings.AWS_STORAGE_BUCKET_NAME,
                    s3_key,
                    ExtraArgs={'ACL': 'public-read'}
                )
                
                # Actualizar sesión
                upload_session.s3_key = s3_key
                upload_session.status = 'completed'
                upload_session.completed_at = timezone.now()
                upload_session.save()
                
                return JsonResponse({
                    'success': True,
                    's3_url': f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_key}"
                })
                
            except ClientError as e:
                upload_session.status = 'failed'
                upload_session.error_message = str(e)
                upload_session.save()
                
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
    
    # Obtener sesiones de subida recientes
    recent_uploads = VideoUploadSession.objects.filter(
        admin_user=request.user
    ).order_by('-started_at')[:10]
    
    context = {
        'recent_uploads': recent_uploads,
    }
    
    return render(request, 'admin_panel/video_upload.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def user_monitoring(request):
    """Monitoreo de actividad de usuarios"""
    user_id = request.GET.get('user_id')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if user_id:
        # Vista específica de un usuario
        user = get_object_or_404(User, id=user_id)
        exercise_logs = ExerciseLog.objects.filter(user=user).order_by('-exercise_date')
        
        # Estadísticas del usuario
        total_exercises = exercise_logs.count()
        this_month = exercise_logs.filter(
            exercise_date__month=timezone.now().month,
            exercise_date__year=timezone.now().year
        ).count()
        
        # Dificultades
        difficulties = exercise_logs.values('difficulty').annotate(count=Count('difficulty'))
        
        context = {
            'selected_user': user,
            'exercise_logs': exercise_logs,
            'total_exercises': total_exercises,
            'this_month': this_month,
            'difficulties': difficulties,
        }
        
        return render(request, 'admin_panel/user_monitoring_detail.html', context)
    
    # Vista general de todos los usuarios
    users = User.objects.select_related('userprofile').prefetch_related('exercise_logs')
    
    # Filtros de fecha
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            users = users.filter(exercise_logs__exercise_date__gte=from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            users = users.filter(exercise_logs__exercise_date__lte=to_date)
        except ValueError:
            pass
    
    # Agregar estadísticas a cada usuario
    for user in users:
        user.exercise_count = user.exercise_logs.count()
        user.last_exercise = user.exercise_logs.order_by('-exercise_date').first()
    
    # Ordenar por actividad
    users = sorted(users, key=lambda x: x.exercise_count, reverse=True)
    
    context = {
        'users': users,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'admin_panel/user_monitoring.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def admin_activity_log(request):
    """Registro de actividades administrativas"""
    admin_filter = request.GET.get('admin', '')
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    activities = AdminActivity.objects.select_related('admin_user')
    
    # Filtros
    if admin_filter:
        activities = activities.filter(admin_user_id=admin_filter)
    
    if action_filter:
        activities = activities.filter(action=action_filter)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            activities = activities.filter(created_at__date__gte=from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            activities = activities.filter(created_at__date__lte=to_date)
        except ValueError:
            pass
    
    # Paginación
    paginator = Paginator(activities, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Filtros disponibles
    admins = User.objects.filter(is_staff=True)
    actions = AdminActivity.ACTION_CHOICES
    
    context = {
        'page_obj': page_obj,
        'admins': admins,
        'actions': actions,
        'admin_filter': admin_filter,
        'action_filter': action_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'admin_panel/activity_log.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def delete_video(request, video_id):
    """Eliminar video de S3 y de la base de datos"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        # Obtener la sesión de video
        upload_session = get_object_or_404(VideoUploadSession, id=video_id, admin_user=request.user)
        
        # Verificar que el video esté completado
        if upload_session.status != 'completed':
            return JsonResponse({'success': False, 'error': 'Solo se pueden eliminar videos completados'})
        
        # Eliminar archivo de S3
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            # Eliminar archivo de S3
            s3_client.delete_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=upload_session.s3_key
            )
            
        except ClientError as e:
            # Si falla la eliminación de S3, continuar con la eliminación de la BD
            print(f"Error eliminando de S3: {e}")
        
        # Eliminar registro de la base de datos
        filename = upload_session.filename
        upload_session.delete()
        
        # Registrar actividad
        AdminActivity.objects.create(
            admin_user=request.user,
            action='video_deleted',
            target_model='VideoUploadSession',
            target_id=video_id,
            details=f'Video eliminado: {filename}'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Video {filename} eliminado exitosamente'
        })
        
    except VideoUploadSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Video no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'})
