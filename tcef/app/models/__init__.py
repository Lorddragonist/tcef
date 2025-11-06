"""
Módulos de modelos organizados por dominio.
Este archivo mantiene la compatibilidad con las importaciones existentes.
"""
from .user import UserProfile, PasswordResetRequest
from .exercise import ExerciseLog
from .routine import WeeklyRoutine
from .body_measurements import BodyMeasurements, BodyCompositionHistory

__all__ = [
    'UserProfile',
    'PasswordResetRequest',
    'ExerciseLog',
    'WeeklyRoutine',
    'BodyMeasurements',
    'BodyCompositionHistory',
]

