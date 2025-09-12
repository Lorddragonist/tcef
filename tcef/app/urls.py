from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('request-password-reset/', views.request_password_reset, name='request_password_reset'),
    path('reset-password/<str:token>/', views.reset_password_with_token, name='reset_password_with_token'),
    path('profile/', views.profile, name='profile'),
    
    # URLs del calendario de ejercicios
    path('calendar/', views.exercise_calendar, name='exercise_calendar'),
    path('calendar/<int:year>/<int:month>/', views.exercise_calendar, name='exercise_calendar_month'),
    path('exercise/add/', views.add_exercise, name='add_exercise'),
    path('exercise/remove/', views.remove_exercise, name='remove_exercise'),
    path('exercise/stats/', views.exercise_stats, name='exercise_stats'),
    
    # URL de logout personalizado
    path('logout/', views.custom_logout, name='custom_logout'),
    
    # Páginas de error y mantenimiento
    path('under-construction/', views.under_construction, name='under_construction'),
    path('test-404/', views.test_404, name='test_404'),  # Para probar la página 404
    
    # Medidas físicas
    path('add-measurements/', views.add_body_measurements, name='add_measurements'),
] 