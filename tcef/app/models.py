"""
Este archivo mantiene compatibilidad hacia atrás.
Los modelos han sido organizados en módulos separados dentro del directorio models/.
Para nuevas importaciones, se recomienda usar: from app.models import ModelName
"""
from .models import (
    UserProfile,
    PasswordResetRequest,
    ExerciseLog,
    WeeklyRoutine,
    BodyMeasurements,
    BodyCompositionHistory,
)

__all__ = [
    'UserProfile',
    'PasswordResetRequest',
    'ExerciseLog',
    'WeeklyRoutine',
    'BodyMeasurements',
    'BodyCompositionHistory',
]
