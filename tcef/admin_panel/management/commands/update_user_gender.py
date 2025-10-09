from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.models import UserProfile

class Command(BaseCommand):
    help = 'Update user gender for existing users without gender'

    def add_arguments(self, parser):
        parser.add_argument(
            '--default-gender',
            type=str,
            choices=['M', 'F'],
            default='M',
            help='Default gender to assign to users without gender (default: M)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )

    def handle(self, *args, **options):
        default_gender = options['default_gender']
        dry_run = options['dry_run']
        
        # Buscar usuarios sin género
        users_without_gender = User.objects.filter(
            userprofile__gender__isnull=True
        ).select_related('userprofile')
        
        count = users_without_gender.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Todos los usuarios ya tienen género asignado.')
            )
            return
        
        self.stdout.write(f'📊 Encontrados {count} usuarios sin género asignado')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 MODO DRY-RUN - No se realizarán cambios')
            )
        
        updated_count = 0
        
        for user in users_without_gender:
            try:
                profile = user.userprofile
                
                if dry_run:
                    self.stdout.write(
                        f'  🔍 Se actualizaría: {user.username} -> Género: {default_gender}'
                    )
                else:
                    profile.gender = default_gender
                    profile.save()
                    self.stdout.write(
                        f'  ✅ Actualizado: {user.username} -> Género: {default_gender}'
                    )
                
                updated_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error actualizando {user.username}: {str(e)}')
                )
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Proceso completado. {updated_count} usuarios actualizados.')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'🔍 DRY-RUN completado. {updated_count} usuarios serían actualizados.')
            )
            self.stdout.write(
                self.style.WARNING('Para aplicar los cambios, ejecuta el comando sin --dry-run')
            )
