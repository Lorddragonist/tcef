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

from .models import UserGroup, UserGroupMembership, CustomRoutine, AdminActivity, VideoUploadSession, Video, RoutineVideo
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
    
    users = User.objects.select_related('userprofile').prefetch_related('group_membership__group')
    
    # Filtros
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if group_filter:
        users = users.filter(group_membership__group_id=group_filter)
    
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
        # Obtener datos del formulario
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Validaciones básicas
        errors = []
        
        if not username:
            errors.append('El nombre de usuario es requerido.')
        elif User.objects.filter(username=username).exists():
            errors.append('Este nombre de usuario ya existe.')
            
        if not email:
            errors.append('El email es requerido.')
        elif User.objects.filter(email=email).exists():
            errors.append('Este email ya está registrado.')
            
        if not password1:
            errors.append('La contraseña es requerida.')
        elif len(password1) < 8:
            errors.append('La contraseña debe tener al menos 8 caracteres.')
        elif password1 != password2:
            errors.append('Las contraseñas no coinciden.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Crear usuario
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True
                )
                
                # Crear perfil de usuario
                profile = UserProfile.objects.create(
                    user=user,
                    is_approved=True,  # Los usuarios creados por admin están aprobados
                    terms_accepted=True,
                    terms_accepted_date=timezone.now()
                )
                
                # Asignar grupo si se especificó
                group_id = request.POST.get('group')
                if group_id:
                    try:
                        group = UserGroup.objects.get(id=group_id)
                        UserGroupMembership.objects.create(user=user, group=group)
                    except UserGroup.DoesNotExist:
                        messages.warning(request, f'El grupo seleccionado no existe. Usuario creado sin grupo.')
                
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
                
            except Exception as e:
                messages.error(request, f'Error al crear el usuario: {str(e)}')
    
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'groups': groups,
    }
    
    return render(request, 'admin_panel/create_user.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def edit_user(request, user_id):
    """Editar usuario"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # Actualizar datos básicos
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        # Actualizar perfil
        try:
            profile = user.userprofile
        except:
            from app.models import UserProfile
            profile = UserProfile.objects.create(user=user)
        
        profile.is_approved = request.POST.get('is_approved') == 'on'
        profile.save()
        
        # Actualizar grupo
        group_id = request.POST.get('group')
        if group_id:
            try:
                group = UserGroup.objects.get(id=group_id)
                
                # Verificar si ya existe una membresía
                try:
                    existing_membership = user.group_membership
                    # Si ya está en el mismo grupo, no hacer nada
                    if existing_membership.group.id == int(group_id):
                        pass  # Ya está en el grupo correcto
                    else:
                        # Cambiar al nuevo grupo
                        existing_membership.group = group
                        existing_membership.save()
                except UserGroupMembership.DoesNotExist:
                    # No tiene membresía, crear una nueva
                    UserGroupMembership.objects.create(user=user, group=group)
                    
            except UserGroup.DoesNotExist:
                messages.error(request, 'El grupo seleccionado no existe.')
            except ValueError:
                messages.error(request, 'ID de grupo inválido.')
        else:
            # Si no se seleccionó grupo, eliminar membresía existente
            try:
                existing_membership = user.group_membership
                existing_membership.delete()
            except UserGroupMembership.DoesNotExist:
                pass  # No tenía membresía
        
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
    
    # Obtener el grupo actual del usuario
    try:
        current_group = user.group_membership.group
        user_group_id = current_group.id
    except UserGroupMembership.DoesNotExist:
        user_group_id = None
    
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'user': user,
        'groups': groups,
        'user_group_id': user_group_id,
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
                color=color,
                is_active=True  # Por defecto activo
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
        elif action == 'toggle':
            group_id = request.POST.get('group_id')
            is_active = request.POST.get('is_active') == 'true'
            
            try:
                group = get_object_or_404(UserGroup, id=group_id)
                group.is_active = is_active
                group.save()
                
                AdminActivity.objects.create(
                    admin_user=request.user,
                    action='group_updated',
                    target_model='UserGroup',
                    target_id=group.id,
                    details=f'Estado del grupo cambiado: {group.name} - {"Activo" if is_active else "Inactivo"}'
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Grupo {group.name} {"activado" if is_active else "desactivado"} exitosamente.'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error al actualizar el grupo: {str(e)}'
                })
    
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
        group_id = request.POST.get('group')
        assigned_date = request.POST.get('assigned_date')
        video_ids = request.POST.getlist('videos')  # Lista de IDs de videos
        
        try:
            group = UserGroup.objects.get(id=group_id)
            
            routine = CustomRoutine.objects.create(
                title=title,
                description=description,
                group=group,
                assigned_date=assigned_date,
                created_by=request.user
            )
            
            # Crear lista de videos con sus órdenes
            video_orders = []
            for video_id in video_ids:
                if video_id:
                    try:
                        video = Video.objects.get(id=video_id)
                        # Obtener el orden personalizado del formulario
                        order_key = f'video_order_{video_id}'
                        order = request.POST.get(order_key, 1)
                        
                        # Convertir a entero y validar
                        try:
                            order = int(order)
                            if order < 1:
                                order = 1
                        except (ValueError, TypeError):
                            order = 1
                        
                        video_orders.append((video, order))
                    except Video.DoesNotExist:
                        pass
            
            # Ordenar por el orden especificado y asignar órdenes únicos
            video_orders.sort(key=lambda x: x[1])  # Ordenar por el orden especificado
            
            # Crear los RoutineVideo con órdenes únicos secuenciales
            for index, (video, original_order) in enumerate(video_orders, 1):
                RoutineVideo.objects.create(
                    routine=routine,
                    video=video,
                    order=index  # Usar índice secuencial para evitar duplicados
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
            
        except UserGroup.DoesNotExist:
            messages.error(request, 'El grupo seleccionado no existe.')
        except Exception as e:
            messages.error(request, f'Error al crear la rutina: {str(e)}')
    
    groups = UserGroup.objects.filter(is_active=True)
    videos = Video.objects.filter(is_active=True).order_by('-created_at')
    
    context = {
        'groups': groups,
        'videos': videos,
    }
    
    return render(request, 'admin_panel/create_routine.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def edit_routine(request, routine_id):
    """Editar rutina existente"""
    routine = get_object_or_404(CustomRoutine, id=routine_id)
    
    if request.method == 'POST':
        # Actualizar campos básicos de la rutina
        routine.title = request.POST.get('title')
        routine.description = request.POST.get('description')
        routine.group_id = request.POST.get('group')
        routine.assigned_date = request.POST.get('assigned_date')
        routine.is_active = request.POST.get('is_active') == 'on'
        routine.save()
        
        # Manejar videos de la rutina
        video_ids = request.POST.getlist('videos')
        
        # Eliminar videos existentes
        routine.routine_videos.all().delete()
        
        # Crear lista de videos con sus órdenes
        video_orders = []
        for video_id in video_ids:
            if video_id:
                try:
                    video = Video.objects.get(id=video_id)
                    # Obtener el orden personalizado del formulario
                    order_key = f'video_order_{video_id}'
                    order = request.POST.get(order_key, 1)
                    
                    # Convertir a entero y validar
                    try:
                        order = int(order)
                        if order < 1:
                            order = 1
                    except (ValueError, TypeError):
                        order = 1
                    
                    video_orders.append((video, order))
                except Video.DoesNotExist:
                    pass
        
        # Ordenar por el orden especificado y asignar órdenes únicos
        video_orders.sort(key=lambda x: x[1])  # Ordenar por el orden especificado
        
        # Crear los RoutineVideo con órdenes únicos secuenciales
        for index, (video, original_order) in enumerate(video_orders, 1):
            RoutineVideo.objects.create(
                routine=routine,
                video=video,
                order=index  # Usar índice secuencial para evitar duplicados
            )
        
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
    videos = Video.objects.filter(is_active=True).order_by('-created_at')
    
    # Obtener IDs de videos actuales para marcar como seleccionados
    current_video_ids = list(routine.routine_videos.values_list('video_id', flat=True))
    
    context = {
        'routine': routine,
        'groups': groups,
        'videos': videos,
        'current_video_ids': current_video_ids,
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
    """Página para subir videos a S3"""
    if request.method == 'POST':
        # Obtener archivo del request
        video_file = request.FILES.get('video')
        title = request.POST.get('title', '')
        description = request.POST.get('description', '')
        
        if video_file:
            # Crear sesión
            upload_session = VideoUploadSession.objects.create(
                admin_user=request.user,
                filename=video_file.name,
                file_size=video_file.size,
                s3_bucket=settings.AWS_STORAGE_BUCKET_NAME,
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
                
                # Crear registro Video
                s3_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_key}"
                
                # Calcular duración del video (por ahora usaremos un valor por defecto)
                duration = 300  # 5 minutos por defecto
                
                video = Video.objects.create(
                    title=title or video_file.name,
                    description=description,
                    filename=video_file.name,
                    s3_key=s3_key,
                    s3_url=s3_url,
                    duration=duration,
                    file_size=video_file.size,
                    upload_session=upload_session,
                    created_by=request.user
                )
                
                # Registrar actividad
                AdminActivity.objects.create(
                    admin_user=request.user,
                    action='video_uploaded',
                    target_model='Video',
                    target_id=video.id,
                    details=f'Video subido: {video.title}'
                )
                
                return JsonResponse({
                    'success': True,
                    's3_url': s3_url,
                    'video_id': video.id,
                    'message': f'Video {video.title} subido exitosamente'
                })
                
            except ClientError as e:
                upload_session.status = 'failed'
                upload_session.error_message = str(e)
                upload_session.save()
                
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
    
    # Obtener videos recientes - Mostrar todos los videos, no solo los del usuario actual
    recent_videos = Video.objects.filter(
        is_active=True
    ).order_by('-created_at')[:10]
    
    context = {
        'recent_videos': recent_videos,
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
        # Obtener la sesión de video - Permitir a cualquier admin eliminar cualquier video
        upload_session = get_object_or_404(VideoUploadSession, id=video_id)
        
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
        return JsonResponse({'success': False, 'error': str(e)})


@user_passes_test(is_staff_user, login_url='/login/')
def routine_details(request, routine_id):
    """Obtener detalles de una rutina para mostrar en modal"""
    try:
        routine = get_object_or_404(CustomRoutine, id=routine_id)
        
        # Obtener videos de la rutina ordenados
        routine_videos = routine.get_videos_ordered()
        
        # Formatear fechas manualmente
        assigned_date_str = routine.assigned_date.strftime("%d/%m/%Y")
        created_date_str = routine.created_at.strftime("%d/%m/%Y %H:%M")
        
        # Generar HTML para el modal
        html_content = f"""
        <div class="row">
            <div class="col-md-6">
                <h6 class="text-primary">Información General</h6>
                <table class="table table-sm">
                    <tr>
                        <td><strong>Título:</strong></td>
                        <td>{routine.title}</td>
                    </tr>
                    <tr>
                        <td><strong>Descripción:</strong></td>
                        <td>{routine.description}</td>
                    </tr>
                    <tr>
                        <td><strong>Grupo:</strong></td>
                        <td>
                            <span class="badge" style="background-color: {routine.group.color}; color: white;">
                                {routine.group.name}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Fecha:</strong></td>
                        <td>{assigned_date_str}</td>
                    </tr>
                    <tr>
                        <td><strong>Estado:</strong></td>
                        <td>
                            <span class="badge bg-{'success' if routine.is_active else 'secondary'}">
                                {'Activa' if routine.is_active else 'Inactiva'}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Creado por:</strong></td>
                        <td>{routine.created_by.username}</td>
                    </tr>
                    <tr>
                        <td><strong>Creado:</strong></td>
                        <td>{created_date_str}</td>
                    </tr>
                </table>
            </div>
            <div class="col-md-6">
                <h6 class="text-primary">Estadísticas</h6>
                <table class="table table-sm">
                    <tr>
                        <td><strong>Total de videos:</strong></td>
                        <td>{routine.get_videos_count()}</td>
                    </tr>
                    <tr>
                        <td><strong>Duración total:</strong></td>
                        <td>{routine.get_total_duration()}</td>
                    </tr>
                </table>
            </div>
        </div>
        """
        
        if routine_videos:
            html_content += f"""
        <hr>
        <h6 class="text-primary">Videos de la Rutina</h6>
        <div class="table-responsive">
            <table class="table table-sm table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>Orden</th>
                        <th>Título</th>
                        <th>Duración</th>
                        <th>Tamaño</th>
                        <th>Preview</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for routine_video in routine_videos:
                video = routine_video.video
                description_snippet = f'<br><small class="text-muted">{video.description[:50]}...</small>' if video.description else ''
                html_content += f"""
                    <tr>
                        <td>
                            <span class="badge bg-primary">{routine_video.order}</span>
                        </td>
                        <td>
                            <strong>{video.title}</strong>
                            {description_snippet}
                        </td>
                        <td>{video.get_duration_formatted()}</td>
                        <td>{video.get_file_size_formatted()}</td>
                        <td>
                            <button type="button" class="btn btn-sm btn-outline-primary" 
                                    onclick="showVideoPreview('{video.s3_url}', '{video.title}')" 
                                    title="Ver preview del video">
                                <i class="fas fa-play"></i>
                            </button>
                        </td>
                    </tr>
                """
            
            html_content += """
                </tbody>
            </table>
        </div>
            """
        else:
            html_content += """
        <hr>
        <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            Esta rutina no tiene videos asignados.
        </div>
            """
        
        return JsonResponse({
            'success': True,
            'html': html_content
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@user_passes_test(is_staff_user, login_url='/login/')
def replicate_routine(request, routine_id):
    """Replicar rutina a otros grupos y fechas"""
    routine = get_object_or_404(CustomRoutine, id=routine_id)
    
    if request.method == 'POST':
        group_ids = request.POST.getlist('groups')
        dates = request.POST.getlist('dates')
        
        if not group_ids or not dates:
            messages.error(request, 'Debes seleccionar al menos un grupo y una fecha.')
            return redirect('admin_panel:replicate_routine', routine_id=routine_id)
        
        try:
            replicated_count = 0
            for group_id in group_ids:
                for date_str in dates:
                    try:
                        group = UserGroup.objects.get(id=group_id)
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                        
                        # Verificar si ya existe una rutina para este grupo y fecha
                        if CustomRoutine.objects.filter(group=group, assigned_date=date_obj).exists():
                            continue  # Saltar si ya existe
                        
                        # Crear nueva rutina
                        new_routine = CustomRoutine.objects.create(
                            title=f"{routine.title} (Replicada)",
                            description=routine.description,
                            group=group,
                            assigned_date=date_obj,
                            created_by=request.user
                        )
                        
                        # Replicar videos con el mismo orden
                        for routine_video in routine.get_videos_ordered():
                            RoutineVideo.objects.create(
                                routine=new_routine,
                                video=routine_video.video,
                                order=routine_video.order,
                                notes=routine_video.notes
                            )
                        
                        replicated_count += 1
                        
                    except (UserGroup.DoesNotExist, ValueError) as e:
                        continue
            
            AdminActivity.objects.create(
                admin_user=request.user,
                action='routine_replicated',
                target_model='CustomRoutine',
                target_id=routine.id,
                details=f'Rutina replicada {replicated_count} veces: {routine.title}'
            )
            
            if replicated_count > 0:
                messages.success(request, f'Rutina replicada exitosamente {replicated_count} veces.')
            else:
                messages.warning(request, 'No se pudo replicar la rutina. Verifica que los grupos y fechas sean válidos.')
            
            return redirect('admin_panel:routine_management')
            
        except Exception as e:
            messages.error(request, f'Error al replicar la rutina: {str(e)}')
    
    groups = UserGroup.objects.filter(is_active=True)
    
    context = {
        'routine': routine,
        'groups': groups,
    }
    
    return render(request, 'admin_panel/replicate_routine.html', context)
