from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Backend de autenticación personalizado que permite login con email o username
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Buscar usuario por username o email
            user = User.objects.get(
                Q(username=username) | Q(email=username)
            )
            
            # Verificar la contraseña
            if user.check_password(password):
                return user
                
        except User.DoesNotExist:
            # Si no se encuentra el usuario, retornar None
            return None
        except User.MultipleObjectsReturned:
            # Si hay múltiples usuarios (caso muy raro), tomar el primero
            user = User.objects.filter(
                Q(username=username) | Q(email=username)
            ).first()
            if user and user.check_password(password):
                return user
            return None
        
        return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
