from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, ExerciseLog, WeeklyRoutine, BodyMeasurements, BodyCompositionHistory, FoodDiary

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil de Usuario'
    fk_name = 'user'  # Especificar cuál ForeignKey usar
    fields = ('gender', 'hipopresivos', 'is_approved', 'approval_date', 'approved_by', 'terms_accepted', 'terms_accepted_date')

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_gender', 'is_staff', 'get_is_approved', 'get_terms_accepted')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'userprofile__gender', 'userprofile__is_approved', 'userprofile__terms_accepted')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    def get_gender(self, obj):
        try:
            return obj.userprofile.get_gender_display()
        except UserProfile.DoesNotExist:
            return 'No especificado'
    get_gender.short_description = 'Sexo'
    
    def get_is_approved(self, obj):
        try:
            return obj.userprofile.is_approved
        except UserProfile.DoesNotExist:
            return False
    get_is_approved.boolean = True
    get_is_approved.short_description = 'Usuario Aprobado'
    
    def get_terms_accepted(self, obj):
        try:
            return obj.userprofile.terms_accepted
        except UserProfile.DoesNotExist:
            return False
    get_terms_accepted.boolean = True
    get_terms_accepted.short_description = 'Términos Aceptados'

class ExerciseLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'exercise_date', 'difficulty', 'completed_at', 'created_at')
    list_filter = ('difficulty', 'exercise_date', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'notes')
    date_hierarchy = 'exercise_date'
    ordering = ('-exercise_date', '-created_at')
    
    fieldsets = (
        ('Información del Usuario', {
            'fields': ('user', 'exercise_date')
        }),
        ('Detalles del Ejercicio', {
            'fields': ('difficulty', 'notes')
        }),
        ('Timestamps', {
            'fields': ('completed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('completed_at', 'created_at', 'updated_at')

class WeeklyRoutineAdmin(admin.ModelAdmin):
    list_display = ('day', 'title', 'duration_formatted', 'is_active', 'created_at')
    list_filter = ('day', 'is_active', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('day',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('day', 'title', 'description', 'is_active')
        }),
        ('Video', {
            'fields': ('video_url', 'duration'),
            'description': 'Ingresa la URL del video en GCP Cloud Storage y la duración en segundos'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def duration_formatted(self, obj):
        return obj.get_duration_formatted()
    duration_formatted.short_description = 'Duración'
    
    actions = ['activate_routines', 'deactivate_routines']
    
    def activate_routines(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} rutina(s) activada(s) exitosamente.')
    activate_routines.short_description = 'Activar rutinas seleccionadas'
    
    def deactivate_routines(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} rutina(s) desactivada(s) exitosamente.')
    deactivate_routines.short_description = 'Desactivar rutinas seleccionadas'

class BodyMeasurementsAdmin(admin.ModelAdmin):
    list_display = ('user', 'measurement_date', 'weight', 'height', 'age', 'waist', 'hip', 'chest', 'bmi', 'waist_hip_ratio', 'created_at')
    list_filter = ('measurement_date', 'created_at', 'user__userprofile__gender')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    date_hierarchy = 'measurement_date'
    ordering = ('-measurement_date', '-created_at')
    
    fieldsets = (
        ('Usuario y Fecha', {
            'fields': ('user', 'measurement_date')
        }),
        ('Medidas Básicas', {
            'fields': ('weight', 'height', 'age')
        }),
        ('Medidas Corporales', {
            'fields': ('waist', 'hip', 'chest')
        }),
        ('Cálculos Automáticos', {
            'fields': ('bmi', 'waist_hip_ratio'),
            'classes': ('collapse',),
            'description': 'Estos valores se calculan automáticamente'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('bmi', 'waist_hip_ratio', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

class BodyCompositionHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'measurement_date', 'imc', 'ica', 'body_fat_percentage', 'muscle_mass', 'created_at')
    list_filter = ('measurement_date', 'created_at', 'user__userprofile__gender')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    date_hierarchy = 'measurement_date'
    ordering = ('-measurement_date', '-created_at')
    
    fieldsets = (
        ('Usuario y Fecha', {
            'fields': ('user', 'measurement_date')
        }),
        ('Composición Corporal', {
            'fields': ('imc', 'ica', 'body_fat_percentage', 'muscle_mass')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

# Desregistrar el User admin por defecto y registrar el personalizado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Registrar los modelos personalizados
admin.site.register(ExerciseLog, ExerciseLogAdmin)
admin.site.register(WeeklyRoutine, WeeklyRoutineAdmin)
admin.site.register(BodyMeasurements, BodyMeasurementsAdmin)
admin.site.register(BodyCompositionHistory, BodyCompositionHistoryAdmin)

class FoodDiaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'meal_date', 'meal_time', 'meal_type', 'description', 'created_at')
    list_filter = ('meal_type', 'meal_date', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'description')
    date_hierarchy = 'meal_date'
    ordering = ('-meal_date', '-meal_time')
    
    fieldsets = (
        ('Usuario y Fecha', {
            'fields': ('user', 'meal_date', 'meal_time')
        }),
        ('Información de la Comida', {
            'fields': ('meal_type', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

admin.site.register(FoodDiary, FoodDiaryAdmin)
