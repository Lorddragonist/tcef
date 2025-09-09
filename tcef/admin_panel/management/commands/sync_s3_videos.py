from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from admin_panel.models import Video, VideoUploadSession
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import os

class Command(BaseCommand):
    help = 'Sincroniza videos existentes de S3 con la base de datos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-user',
            type=str,
            default='admin',
            help='Username del admin que será asignado como creador de los videos'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra qué videos se procesarían sin crear registros'
        )

    def handle(self, *args, **options):
        admin_username = options['admin_user']
        dry_run = options['dry_run']
        
        try:
            # Obtener usuario admin
            try:
                admin_user = User.objects.get(username=admin_username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Usuario admin "{admin_username}" no encontrado')
                )
                return

            # Configurar cliente S3
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )

            # Listar objetos en la carpeta videos/
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            prefix = 'videos/'
            
            self.stdout.write(f'Buscando videos en S3 bucket: {bucket_name}')
            self.stdout.write(f'Prefijo: {prefix}')
            
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            videos_processed = 0
            videos_created = 0
            videos_skipped = 0
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    # Saltar carpetas
                    if obj['Key'].endswith('/'):
                        continue
                    
                    # Solo procesar archivos de video
                    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
                    if not any(obj['Key'].lower().endswith(ext) for ext in video_extensions):
                        continue
                    
                    videos_processed += 1
                    
                    # Extraer información del archivo
                    filename = os.path.basename(obj['Key'])
                    file_size = obj['Size']
                    s3_key = obj['Key']
                    s3_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_key}"
                    
                    # Verificar si ya existe en la base de datos
                    if Video.objects.filter(s3_key=s3_key).exists():
                        self.stdout.write(f'  ⏭️  Saltando: {filename} (ya existe)')
                        videos_skipped += 1
                        continue
                    
                    if dry_run:
                        self.stdout.write(f'  🔍 [DRY RUN] Procesaría: {filename}')
                        videos_created += 1
                        continue
                    
                    try:
                        # Crear sesión de subida simulada
                        upload_session = VideoUploadSession.objects.create(
                            admin_user=admin_user,
                            filename=filename,
                            file_size=file_size,
                            s3_bucket=bucket_name,
                            s3_key=s3_key,
                            status='completed',
                            completed_at=datetime.now()
                        )
                        
                        # Crear registro de video
                        video = Video.objects.create(
                            title=filename.rsplit('.', 1)[0],  # Nombre sin extensión
                            description=f'Video sincronizado desde S3: {filename}',
                            filename=filename,
                            s3_key=s3_key,
                            s3_url=s3_url,
                            duration=300,  # 5 minutos por defecto
                            file_size=file_size,
                            upload_session=upload_session,
                            created_by=admin_user
                        )
                        
                        self.stdout.write(f'  ✅ Creado: {filename}')
                        videos_created += 1
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Error procesando {filename}: {str(e)}')
                        )
            
            # Resumen
            self.stdout.write('\n' + '='*50)
            self.stdout.write('RESUMEN DE SINCRONIZACIÓN')
            self.stdout.write('='*50)
            self.stdout.write(f'Videos procesados: {videos_processed}')
            self.stdout.write(f'Videos creados: {videos_created}')
            self.stdout.write(f'Videos saltados: {videos_skipped}')
            
            if dry_run:
                self.stdout.write(self.style.WARNING('\n⚠️  MODO DRY RUN - No se crearon registros'))
            else:
                self.stdout.write(self.style.SUCCESS(f'\n✅ Sincronización completada exitosamente'))
                
        except ClientError as e:
            self.stdout.write(
                self.style.ERROR(f'Error de S3: {str(e)}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error general: {str(e)}')
            )
