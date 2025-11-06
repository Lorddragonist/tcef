"""
Este archivo mantiene compatibilidad hacia atrás.
Los modelos han sido organizados en módulos separados dentro del directorio models/.
Para nuevas importaciones, se recomienda usar: from admin_panel.models import ModelName
"""
from .models import (
    UserGroup,
    UserGroupMembership,
    CustomRoutine,
    RoutineVideo,
    Video,
    VideoUploadSession,
    UserApprovalRequest,
    PasswordResetApproval,
    AdminActivity,
)

__all__ = [
    'UserGroup',
    'UserGroupMembership',
    'CustomRoutine',
    'RoutineVideo',
    'Video',
    'VideoUploadSession',
    'UserApprovalRequest',
    'PasswordResetApproval',
    'AdminActivity',
]
