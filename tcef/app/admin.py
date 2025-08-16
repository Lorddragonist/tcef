from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, ExerciseLog

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil de Usuario'
    fields = ('email_confirmed', 'terms_accepted', 'terms_accepted_date', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'date_joined', 'userprofile__email_confirmed')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'email', 'password1', 'password2'),
        }),
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_confirmed', 'terms_accepted', 'created_at', 'updated_at')
    list_filter = ('email_confirmed', 'terms_accepted', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Estado de la Cuenta', {
            'fields': ('email_confirmed', 'email_confirmation_token')
        }),
        ('Términos y Condiciones', {
            'fields': ('terms_accepted', 'terms_accepted_date')
        }),
        ('Información Temporal', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(ExerciseLog)
class ExerciseLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'exercise_date', 'difficulty', 'completed_at', 'has_notes')
    list_filter = ('difficulty', 'exercise_date', 'completed_at', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'notes')
    readonly_fields = ('completed_at', 'created_at', 'updated_at')
    ordering = ('-exercise_date',)
    date_hierarchy = 'exercise_date'
    
    fieldsets = (
        ('Información del Usuario', {
            'fields': ('user',)
        }),
        ('Detalles del Ejercicio', {
            'fields': ('exercise_date', 'difficulty', 'notes')
        }),
        ('Información Temporal', {
            'fields': ('completed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_notes(self, obj):
        """Indica si el ejercicio tiene notas"""
        return bool(obj.notes and obj.notes.strip())
    has_notes.boolean = True
    has_notes.short_description = 'Tiene Notas'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def get_list_display(self, request):
        """Personalizar la lista según el usuario"""
        if request.user.is_superuser:
            return ('user', 'exercise_date', 'difficulty', 'completed_at', 'has_notes', 'created_at')
        return ('user', 'exercise_date', 'difficulty', 'completed_at', 'has_notes')
    
    def get_queryset(self, request):
        """Filtrar por usuario si no es superusuario"""
        qs = super().get_queryset(request).select_related('user')
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs

# Re-registrar el modelo User con nuestro UserAdmin personalizado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
