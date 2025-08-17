from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('confirm-email/<str:token>/', views.confirm_email, name='confirm_email'),
    path('profile/', views.profile, name='profile'),
    
    # URLs del calendario de ejercicios
    path('calendar/', views.exercise_calendar, name='exercise_calendar'),
    path('calendar/<int:year>/<int:month>/', views.exercise_calendar, name='exercise_calendar_month'),
    path('exercise/add/', views.add_exercise, name='add_exercise'),
    path('exercise/remove/', views.remove_exercise, name='remove_exercise'),
    path('exercise/stats/', views.exercise_stats, name='exercise_stats'),
    
    # URLs de las rutinas semanales
    path('routines/', views.weekly_routines, name='weekly_routines'),
    path('routines/<str:day>/', views.weekly_routines, name='weekly_routines_day'),
    path('routines/complete/', views.complete_routine, name='complete_routine'),
    
    # URL de logout personalizado
    path('logout/', views.custom_logout, name='custom_logout'),
] 