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
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
import json
from datetime import datetime, timedelta

from .models import UserGroup, UserGroupMembership, CustomRoutine, AdminActivity, VideoUploadSession, Video, RoutineVideo, PasswordResetApproval, UserApprovalRequest
from app.models import UserProfile, ExerciseLog, BodyMeasurements, BodyCompositionHistory, FoodDiary

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
        gender = request.POST.get('gender')
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
            
        if not gender:
            errors.append('El género es requerido.')
        elif gender not in ['M', 'F']:
            errors.append('El género seleccionado no es válido.')
            
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
                
                # Obtener el valor de hipopresivos del formulario
                hipopresivos = request.POST.get('hipopresivos') == 'on'
                
                # Crear perfil de usuario
                profile = UserProfile.objects.create(
                    user=user,
                    is_approved=True,  # Los usuarios creados por admin están aprobados
                    terms_accepted=True,
                    terms_accepted_date=timezone.now(),
                    gender=gender,  # Asignar el género seleccionado
                    hipopresivos=hipopresivos  # Asignar el valor de hipopresivos
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
        user.is_active = request.POST.get('is_active') == 'on'
        user.save()
        
        # Actualizar perfil
        try:
            profile = user.userprofile
        except:
            from app.models import UserProfile
            profile = UserProfile.objects.create(user=user)
        
        profile.is_approved = request.POST.get('is_approved') == 'on'
        # Agregar el campo de género
        profile.gender = request.POST.get('gender', '')
        # Agregar el campo de hipopresivos
        profile.hipopresivos = request.POST.get('hipopresivos') == 'on'
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
def video_management(request):
    """Gestión de videos - Listar, editar y eliminar videos"""
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    order_by = request.GET.get('order_by', '-created_at')  # Por defecto ordenar por fecha descendente
    
    videos = Video.objects.select_related('created_by', 'upload_session').all()
    
    # Filtros
    if search_query:
        videos = videos.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(filename__icontains=search_query)
        )
    
    if status_filter == 'active':
        videos = videos.filter(is_active=True)
    elif status_filter == 'inactive':
        videos = videos.filter(is_active=False)
    
    # Ordenamiento
    # Validar que order_by sea un campo válido
    valid_orders = ['title', '-title', 'created_at', '-created_at', 'filename', '-filename']
    if order_by not in valid_orders:
        order_by = '-created_at'
    
    videos = videos.order_by(order_by)
    
    # Paginación
    paginator = Paginator(videos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Determinar el siguiente orden para el botón
    if order_by == 'title':
        next_order = '-title'
        order_icon = 'fa-sort-alpha-down'
        order_text = 'A-Z'
    elif order_by == '-title':
        next_order = 'title'
        order_icon = 'fa-sort-alpha-up'
        order_text = 'Z-A'
    else:
        next_order = 'title'
        order_icon = 'fa-sort-alpha-down'
        order_text = 'Ordenar A-Z'
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'order_by': order_by,
        'next_order': next_order,
        'order_icon': order_icon,
        'order_text': order_text,
    }
    
    return render(request, 'admin_panel/video_management.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def edit_video(request, video_id):
    """Editar video - Solo título y descripción"""
    video = get_object_or_404(Video, id=video_id)
    
    if request.method == 'POST':
        video.title = request.POST.get('title', '')
        video.description = request.POST.get('description', '')
        video.is_active = request.POST.get('is_active') == 'on'
        video.save()
        
        # Registrar actividad
        AdminActivity.objects.create(
            admin_user=request.user,
            action='video_updated',
            target_model='Video',
            target_id=video.id,
            details=f'Video actualizado: {video.title}'
        )
        
        messages.success(request, f'Video "{video.title}" actualizado exitosamente.')
        return redirect('admin_panel:video_management')
    
    context = {
        'video': video,
    }
    
    return render(request, 'admin_panel/edit_video.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def delete_video(request, video_id):
    """Eliminar video de S3 y de la base de datos"""
    if request.method != 'POST':
        # Si es una solicitud AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': 'Método no permitido'})
        # Si no es AJAX, mostrar página de confirmación
        video = get_object_or_404(Video, id=video_id)
        routine_videos = RoutineVideo.objects.filter(video=video)
        is_used = routine_videos.exists()
        context = {
            'video': video,
            'is_used': is_used,
            'routine_videos': routine_videos.select_related('routine') if is_used else [],
        }
        return render(request, 'admin_panel/delete_video.html', context)
    
    # Método POST - Eliminar video
    video = get_object_or_404(Video, id=video_id)
    video_title = video.title
    s3_error = None
    
    # Intentar eliminar el archivo de S3
    if video.s3_key:
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            try:
                s3_client.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=video.s3_key
                )
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', str(e))
                
                # Manejar diferentes tipos de errores de AWS
                if error_code == 'AccessDenied':
                    s3_error = f'Permisos insuficientes en AWS S3. No se puede eliminar el archivo. Error: {error_message}'
                elif error_code == 'NoSuchKey':
                    s3_error = f'El archivo no existe en S3. Puede que ya haya sido eliminado. Error: {error_message}'
                else:
                    s3_error = f'Error al eliminar archivo de S3 ({error_code}): {error_message}'
                
                print(f"Error eliminando de S3: {error_code} - {error_message}")
        except Exception as e:
            s3_error = f'Error al conectar con AWS S3: {str(e)}'
            print(f"Error de conexión con S3: {e}")
    
    # Eliminar el registro de la base de datos (incluso si falló S3)
    video.delete()
    
    # Registrar actividad
    AdminActivity.objects.create(
        admin_user=request.user,
        action='video_deleted',
        target_model='Video',
        target_id=video_id,
        details=f'Video eliminado: {video_title}'
    )
    
    # Si es una solicitud AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        if s3_error:
            return JsonResponse({
                'success': True,
                'message': f'Video "{video_title}" eliminado de la base de datos, pero hubo un problema al eliminar de S3: {s3_error}',
                'warning': s3_error
            })
        return JsonResponse({
            'success': True,
            'message': f'Video "{video_title}" eliminado exitosamente'
        })
    
    # Si no es AJAX, usar mensajes de Django y redirigir
    if s3_error:
        messages.warning(request, f'Video eliminado, pero hubo un problema con S3: {s3_error}')
    else:
        messages.success(request, f'Video "{video_title}" eliminado exitosamente.')
    return redirect('admin_panel:video_management')
    
    # Verificar si el video está siendo usado en alguna rutina
    routine_videos = RoutineVideo.objects.filter(video=video)
    is_used = routine_videos.exists()
    
    context = {
        'video': video,
        'is_used': is_used,
        'routine_videos': routine_videos.select_related('routine') if is_used else [],
    }
    
    return render(request, 'admin_panel/delete_video.html', context)


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


@user_passes_test(is_staff_user, login_url='/login/')
def user_monitoring(request):
    """Vista principal de monitoreo de usuarios con tabla de métricas del mes actual"""
    from datetime import date
    from django.db.models import Count, Q, Avg, Max
    
    # Obtener el mes actual
    current_date = timezone.now().date()
    current_year = current_date.year
    current_month = current_date.month
    
    # Obtener todos los usuarios con perfil aprobado
    users = User.objects.filter(
        userprofile__is_approved=True
    ).select_related('userprofile').prefetch_related(
        'exercise_logs', 'body_measurements', 'body_composition_history'
    )
    
    # Calcular métricas para cada usuario del mes actual
    user_metrics = []
    
    for user in users:
        # Ejercicios del mes actual
        month_exercises = ExerciseLog.get_month_exercises(user, current_year, current_month)
        exercise_count = month_exercises.count()
        
        # Calcular días laborables del mes (lunes a viernes)
        import calendar
        month_days = calendar.monthrange(current_year, current_month)[1]
        weekdays_in_month = 0
        for day in range(1, month_days + 1):
            if calendar.weekday(current_year, current_month, day) < 5:  # 0-4 = lunes a viernes
                weekdays_in_month += 1
        
        # Racha actual (semanas consecutivas con 5+ ejercicios)
        current_streak = ExerciseLog.get_current_week_streak(user)
        
        # Mejor racha (semanas consecutivas con 5+ ejercicios)
        best_streak = ExerciseLog.get_longest_week_streak(user)
        
        # Medidas más recientes (sin importar el mes, las últimas que haya ingresado)
        latest_measurement = BodyMeasurements.objects.filter(user=user).order_by('-measurement_date').first()
        latest_composition = BodyCompositionHistory.objects.filter(user=user).order_by('-measurement_date').first()
        
        # Progreso mensual basado en días laborables (igual que en exercise_stats)
        monthly_progress = min((exercise_count / weekdays_in_month * 100), 100) if weekdays_in_month > 0 else 0
        
        user_metrics.append({
            'user': user,
            'exercise_count': exercise_count,
            'current_streak': current_streak,
            'best_streak': best_streak,
            'monthly_progress': round(monthly_progress, 1),
            'latest_weight': latest_measurement.weight if latest_measurement else None,
            'latest_bmi': latest_measurement.bmi if latest_measurement else None,
            'latest_body_fat': latest_composition.body_fat_percentage if latest_composition else None,
            'latest_muscle': latest_composition.muscle_mass if latest_composition else None,
            'latest_ica': latest_composition.ica if latest_composition else None,
        })
    
    # Ordenar por progreso mensual descendente
    user_metrics.sort(key=lambda x: x['monthly_progress'], reverse=True)
    
    context = {
        'user_metrics': user_metrics,
        'current_year': current_year,
        'current_month': current_month,
        'current_date': current_date,
    }
    
    return render(request, 'admin_panel/user_monitoring.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def user_detail_modal(request, user_id):
    """Vista AJAX para obtener detalles de un usuario específico"""
    from datetime import date, timedelta
    from django.db.models import Count, Q
    
    user = get_object_or_404(User, id=user_id)
    
    # Obtener parámetros de fecha
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Ejercicios del mes seleccionado
    month_exercises = ExerciseLog.get_month_exercises(user, year, month)
    exercise_dates = [ex.exercise_date.day for ex in month_exercises]  # Solo los días del mes
    
    # Generar calendario tradicional con semanas en filas
    import calendar
    cal = calendar.monthcalendar(year, month)
    day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    # Crear estructura de calendario tradicional: semanas en filas
    calendar_weeks = []
    for week in cal:
        week_days = []
        for day in week:
            if day != 0:  # Día del mes actual
                day_date = date(year, month, day)
                weekday = day_date.weekday()  # 0=Lunes, 6=Domingo
                has_exercise = day in exercise_dates
                week_days.append({
                    'day': day,
                    'weekday': weekday,
                    'weekday_name': day_names[weekday],
                    'has_exercise': has_exercise,
                    'is_current_month': True
                })
            else:  # Día de otro mes (para completar la semana)
                week_days.append({
                    'day': None,
                    'weekday': None,
                    'weekday_name': '',
                    'has_exercise': False,
                    'is_current_month': False
                })
        calendar_weeks.append(week_days)
    
    reordered_day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    # Debug: imprimir información para verificar (solo en desarrollo)
    # print(f"Debug - User: {user.username}, Year: {year}, Month: {month}")
    # print(f"Debug - Exercise dates found: {exercise_dates}")
    # print(f"Debug - Total exercises: {month_exercises.count()}")
    
    # Estadísticas del mes
    total_exercises = month_exercises.count()
    days_in_month = 30  # Aproximación
    exercise_percentage = (total_exercises / days_in_month * 100) if days_in_month > 0 else 0
    
    # Racha actual y mejor racha (semanas consecutivas con 5+ ejercicios)
    current_streak = ExerciseLog.get_current_week_streak(user)
    best_streak = ExerciseLog.get_longest_week_streak(user)
    
    # Medidas corporales del mes (para la tabla detallada)
    month_measurements = BodyMeasurements.objects.filter(
        user=user,
        measurement_date__year=year,
        measurement_date__month=month
    ).order_by('measurement_date')
    
    # Composición corporal del mes (para la tabla detallada)
    month_composition = BodyCompositionHistory.objects.filter(
        user=user,
        measurement_date__year=year,
        measurement_date__month=month
    ).order_by('measurement_date')
    
    # Obtener el ÚLTIMO registro de medidas (independiente del mes seleccionado)
    latest_measurement = BodyMeasurements.objects.filter(
        user=user
    ).order_by('-measurement_date').first()
    
    # Obtener el ÚLTIMO registro de composición (independiente del mes seleccionado)
    latest_composition = BodyCompositionHistory.objects.filter(
        user=user
    ).order_by('-measurement_date').first()
    
    # Si no hay datos del mes, obtener los más recientes disponibles para la tabla
    if not month_measurements.exists():
        month_measurements = BodyMeasurements.objects.filter(user=user).order_by('-measurement_date')[:10]
    
    if not month_composition.exists():
        month_composition = BodyCompositionHistory.objects.filter(user=user).order_by('-measurement_date')[:10]
    
    # Datos para gráficos - OBTENER TODAS LAS MEDIDAS DESDE EL ORIGEN (no solo del mes)
    # Esto permite ver el progreso completo del usuario desde su primera medida
    all_measurements = BodyMeasurements.objects.filter(
        user=user
    ).order_by('measurement_date')  # Ordenar por fecha ascendente para ver el progreso
    
    all_composition = BodyCompositionHistory.objects.filter(
        user=user
    ).order_by('measurement_date')  # Ordenar por fecha ascendente para ver el progreso
    
    # Construir datos para gráficos con TODAS las medidas históricas
    weight_data = []
    bmi_data = []
    body_fat_data = []
    muscle_data = []
    ica_data = []
    
    for measurement in all_measurements:
        weight_data.append({
            'date': measurement.measurement_date.strftime('%Y-%m-%d'),
            'weight': float(measurement.weight),
            'bmi': float(measurement.bmi)
        })
    
    for composition in all_composition:
        if composition.body_fat_percentage:
            body_fat_data.append({
                'date': composition.measurement_date.strftime('%Y-%m-%d'),
                'body_fat': float(composition.body_fat_percentage)
            })
        if composition.muscle_mass:
            muscle_data.append({
                'date': composition.measurement_date.strftime('%Y-%m-%d'),
                'muscle': float(composition.muscle_mass)
            })
        if composition.ica:
            ica_data.append({
                'date': composition.measurement_date.strftime('%Y-%m-%d'),
                'ica': float(composition.ica)
            })
    
    # Estadísticas generales del usuario
    total_exercises_all_time = ExerciseLog.objects.filter(user=user).count()
    first_exercise = ExerciseLog.objects.filter(user=user).order_by('exercise_date').first()
    current_date = timezone.now().date()
    days_since_start = (current_date - first_exercise.exercise_date).days if first_exercise else 0
    
    # Crear objeto de fecha para el mes actual
    from datetime import date
    month_date = date(year, month, 1)
    
    # Obtener la primera fecha de medida del usuario
    first_measurement = BodyMeasurements.objects.filter(user=user).order_by('measurement_date').first()
    first_measurement_date = first_measurement.measurement_date if first_measurement else date.today()
    
    # Fecha de hoy
    today_date = date.today()
    
    # Obtener alimentos registrados en las últimas semanas (últimas 4 semanas)
    weeks_back = 4
    start_date = today_date - timedelta(weeks=weeks_back)
    recent_food_entries = FoodDiary.objects.filter(
        user=user,
        meal_date__gte=start_date
    ).order_by('-meal_date', '-meal_time')[:50]  # Limitar a 50 entradas más recientes
    
    # Agrupar alimentos por semana
    food_by_week = {}
    for entry in recent_food_entries:
        week_num = FoodDiary.get_current_week_number(entry.meal_date)
        week_key = f"{entry.meal_date.year}-W{week_num}"
        if week_key not in food_by_week:
            week_start, week_end = FoodDiary.get_week_dates(entry.meal_date.year, week_num)
            food_by_week[week_key] = {
                'week_start': week_start,
                'week_end': week_end,
                'week_num': week_num,
                'year': entry.meal_date.year,
                'entries': []
            }
        food_by_week[week_key]['entries'].append(entry)
    
    # Ordenar semanas por fecha (más reciente primero)
    food_by_week_list = sorted(food_by_week.values(), key=lambda x: (x['year'], x['week_num']), reverse=True)
    
    # Debug: imprimir información de datos
    print(f"Debug - Usuario: {user.username}")
    print(f"Debug - Medidas del mes: {month_measurements.count()}")
    print(f"Debug - Composición del mes: {month_composition.count()}")
    print(f"Debug - TOTAL medidas históricas para gráficos: {all_measurements.count()}")
    print(f"Debug - TOTAL composición histórica para gráficos: {all_composition.count()}")
    print(f"Debug - weight_data (histórico completo): {len(weight_data)} registros")
    print(f"Debug - body_fat_data (histórico completo): {len(body_fat_data)} registros")
    print(f"Debug - muscle_data (histórico completo): {len(muscle_data)} registros")
    print(f"Debug - ica_data (histórico completo): {len(ica_data)} registros")
    print(f"Debug - Entradas de alimentos: {recent_food_entries.count()}")
    
    # Serializar datos para JavaScript
    import json
    
    context = {
        'user': user,
        'year': year,
        'month': month,
        'month_date': month_date,  # Objeto de fecha para el template
        'exercise_dates': exercise_dates,
        'calendar_weeks': calendar_weeks,  # Calendario tradicional con semanas en filas
        'day_names': reordered_day_names,  # Nombres de días
        'total_exercises': total_exercises,
        'exercise_percentage': round(exercise_percentage, 1),
        'current_streak': current_streak,
        'best_streak': best_streak,
        'month_measurements': month_measurements,
        'month_composition': month_composition,
        'latest_measurement': latest_measurement,
        'latest_composition': latest_composition,
        'weight_data': json.dumps(weight_data),
        'body_fat_data': json.dumps(body_fat_data),
        'muscle_data': json.dumps(muscle_data),
        'ica_data': json.dumps(ica_data),
        'total_exercises_all_time': total_exercises_all_time,
        'days_since_start': days_since_start,
        'first_measurement_date': first_measurement_date,
        'today_date': today_date,
        'food_by_week': food_by_week_list,
        'total_food_entries': recent_food_entries.count(),
    }
    
    return render(request, 'admin_panel/user_detail_modal.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def create_test_data(request):
    """Función temporal para crear datos de prueba"""
    from datetime import date, timedelta
    from app.models import ExerciseLog, BodyMeasurements, BodyCompositionHistory
    
    # Obtener el primer usuario aprobado
    try:
        user = User.objects.filter(userprofile__is_approved=True).first()
        if not user:
            return JsonResponse({'error': 'No hay usuarios aprobados'})
        
        # Crear algunos ejercicios de prueba para el mes actual
        today = date.today()
        current_year = today.year
        current_month = today.month
        
        # Crear ejercicios para algunos días del mes
        test_dates = [
            today - timedelta(days=1),  # Ayer
            today - timedelta(days=2),  # Anteayer
            today - timedelta(days=5),  # Hace 5 días
            today - timedelta(days=7),  # Hace una semana
            today - timedelta(days=10), # Hace 10 días
        ]
        
        created_exercises = []
        for test_date in test_dates:
            if test_date.month == current_month and test_date.year == current_year:
                exercise, created = ExerciseLog.objects.get_or_create(
                    user=user,
                    exercise_date=test_date,
                    defaults={
                        'difficulty': 'medio',
                        'notes': 'Ejercicio de prueba creado automáticamente'
                    }
                )
                if created:
                    created_exercises.append(exercise)
        
        # Crear algunas medidas corporales de prueba
        test_measurement, created = BodyMeasurements.objects.get_or_create(
            user=user,
            measurement_date=today,
            defaults={
                'weight': 70.5,
                'height': 170.0,
                'age': 30,
                'waist': 80.0,
                'hip': 95.0,
                'chest': 90.0
            }
        )
        
        # Crear composición corporal de prueba
        test_composition, created = BodyCompositionHistory.objects.get_or_create(
            user=user,
            measurement_date=today,
            defaults={
                'imc': 24.4,
                'ica': 0.47,
                'body_fat_percentage': 18.5,
                'muscle_mass': 35.2
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Datos de prueba creados para {user.username}',
            'exercises_created': len(created_exercises),
            'measurement_created': created,
            'composition_created': created
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)})


@user_passes_test(is_staff_user, login_url='/login/')
def notifications(request):
    """Vista para mostrar todas las notificaciones pendientes"""
    # Obtener solicitudes de reseteo de contraseña pendientes
    password_reset_pending = PasswordResetApproval.objects.filter(
        status='pending'
    ).select_related('reset_request__user').order_by('-reset_request__requested_at')
    
    # Obtener solicitudes de aprobación de usuarios pendientes
    user_approval_pending = UserApprovalRequest.objects.filter(
        status='pending'
    ).select_related('user', 'user__userprofile').order_by('-requested_at')
    
    context = {
        'password_reset_pending': password_reset_pending,
        'user_approval_pending': user_approval_pending,
        'total_pending': password_reset_pending.count() + user_approval_pending.count(),
    }
    
    return render(request, 'admin_panel/notifications.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def approve_password_reset(request, approval_id):
    """Aprobar solicitud de reseteo de contraseña"""
    approval = get_object_or_404(PasswordResetApproval, id=approval_id, status='pending')
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        approval.approve(request.user, notes)
        
        # Generar URL de reseteo
        reset_request = approval.reset_request
        reset_url = request.build_absolute_uri(
            reverse('app:reset_password_with_token', args=[reset_request.reset_token])
        )
        
        # Enviar email con el enlace de reseteo
        email_sent = False
        email_error = None
        try:
            send_mail(
                subject='Reseteo de Contraseña Aprobado - TCEF',
                message=f'''
Hola {reset_request.user.get_full_name() or reset_request.user.username},

Tu solicitud de reseteo de contraseña ha sido aprobada por el administrador.

Para cambiar tu contraseña, haz clic en el siguiente enlace (válido por 24 horas):

{reset_url}

Si no solicitaste este reseteo, puedes ignorar este email.

Saludos,
Equipo TCEF
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reset_request.user.email],
                fail_silently=False,
            )
            email_sent = True
        except Exception as e:
            email_error = str(e)
        
        # Registrar actividad
        AdminActivity.objects.create(
            admin_user=request.user,
            action='pwd_reset_approved',
            target_model='PasswordResetApproval',
            target_id=approval.id,
            details=f'Reseteo de contraseña aprobado para {approval.reset_request.user.username}'
        )
        
        # Mostrar página de confirmación con la URL
        context = {
            'approval': approval,
            'reset_url': reset_url,
            'email_sent': email_sent,
            'email_error': email_error,
        }
        return render(request, 'admin_panel/password_reset_approved.html', context)
    
    context = {
        'approval': approval,
    }
    
    return render(request, 'admin_panel/approve_password_reset.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def reject_password_reset(request, approval_id):
    """Rechazar solicitud de reseteo de contraseña"""
    approval = get_object_or_404(PasswordResetApproval, id=approval_id, status='pending')
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        approval.reject(request.user, notes)
        
        # Registrar actividad
        AdminActivity.objects.create(
            admin_user=request.user,
            action='pwd_reset_rejected',
            target_model='PasswordResetApproval',
            target_id=approval.id,
            details=f'Reseteo de contraseña rechazado para {approval.reset_request.user.username}'
        )
        
        messages.success(request, f'Reseteo de contraseña rechazado para {approval.reset_request.user.username}.')
        return redirect('admin_panel:notifications')
    
    context = {
        'approval': approval,
    }
    
    return render(request, 'admin_panel/reject_password_reset.html', context)


@user_passes_test(is_staff_user, login_url='/login/')
def get_notifications_count(request):
    """Vista AJAX para obtener el conteo de notificaciones pendientes"""
    password_reset_count = PasswordResetApproval.objects.filter(status='pending').count()
    user_approval_count = UserApprovalRequest.objects.filter(status='pending').count()
    total = password_reset_count + user_approval_count
    
    return JsonResponse({
        'total': total,
        'password_reset': password_reset_count,
        'user_approval': user_approval_count,
    })
