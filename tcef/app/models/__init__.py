"""
Módulos de modelos organizados por dominio.
Este archivo mantiene la compatibilidad con las importaciones existentes.
"""
from .user import UserProfile, PasswordResetRequest
from .exercise import ExerciseLog
from .routine import WeeklyRoutine
from .body_measurements import BodyMeasurements, BodyCompositionHistory
from .food_diary import FoodDiary

__all__ = [
    'UserProfile',
    'PasswordResetRequest',
    'ExerciseLog',
    'WeeklyRoutine',
    'BodyMeasurements',
    'BodyCompositionHistory',
    'FoodDiary',
]

