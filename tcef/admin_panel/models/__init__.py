"""
Módulos de modelos organizados por dominio.
Este archivo mantiene la compatibilidad con las importaciones existentes.
"""
from .groups import UserGroup, UserGroupMembership
from .routines import CustomRoutine, RoutineVideo
from .videos import Video, VideoUploadSession
from .approvals import UserApprovalRequest, PasswordResetApproval
from .audit import AdminActivity

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

