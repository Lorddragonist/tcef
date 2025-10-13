from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import UserProfile
from django.utils import timezone

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu@email.com'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu nombre'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu apellido'
        })
    )
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu contraseña'
        })
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirma tu contraseña'
        })
    )
    terms_accepted = forms.BooleanField(
        required=True,
        label='Acepto los términos y condiciones',
        error_messages={
            'required': 'Debes aceptar los términos y condiciones para continuar.'
        }
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar widgets
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Nombre de usuario'
        })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Este email ya está registrado.')
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError('Las contraseñas no coinciden.')
        
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Crear perfil de usuario
            profile = UserProfile.objects.create(
                user=user,
                terms_accepted=True,
                terms_accepted_date=timezone.now()
            )
            # Generar token de confirmación
            profile.generate_confirmation_token()
        
        return user 

class CustomLoginForm(forms.Form):
    """Formulario personalizado de login que acepta username o email"""
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu nombre de usuario o email',
            'autofocus': True
        }),
        label='Nombre de Usuario o Email'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu contraseña'
        }),
        label='Contraseña'
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Recordarme'
    )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError('Este campo es requerido.')
        return username
    
    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password:
            raise forms.ValidationError('Este campo es requerido.')
        return password 
    

from .models import BodyMeasurements

class BodyMeasurementsForm(forms.ModelForm):
    class Meta:
        model = BodyMeasurements
        fields = ['measurement_date', 'weight', 'height', 'age', 'waist', 'hip', 'chest']
        widgets = {
            'measurement_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'placeholder': 'Ej: 70.5'
            }),
            'height': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'placeholder': 'Ej: 175.0'
            }),
            'age': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '120',
                'placeholder': 'Ej: 25'
            }),
            'waist': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'placeholder': 'Ej: 80.0'
            }),
            'hip': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'placeholder': 'Ej: 95.0'
            }),
            'chest': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'placeholder': 'Ej: 100.0'
            }),
        }
        labels = {
            'measurement_date': 'Fecha de Medición',
            'weight': 'Peso (kg)',
            'height': 'Altura (cm)',
            'age': 'Edad (años)',
            'waist': 'Cintura (cm)',
            'hip': 'Cadera (cm)',
            'chest': 'Cuello (cm)',
        }
    
    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight is not None and weight <= 0:
            raise forms.ValidationError('El peso debe ser mayor a 0.')
        if weight is not None and weight > 500:
            raise forms.ValidationError('El peso debe ser menor a 500 kg.')
        return weight
    
    def clean_height(self):
        height = self.cleaned_data.get('height')
        if height is not None and height <= 0:
            raise forms.ValidationError('La altura debe ser mayor a 0.')
        if height is not None and height > 300:
            raise forms.ValidationError('La altura debe ser menor a 300 cm.')
        return height
    
    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is not None and age <= 0:
            raise forms.ValidationError('La edad debe ser mayor a 0.')
        if age is not None and age > 120:
            raise forms.ValidationError('La edad debe ser menor a 120 años.')
        return age
    
    def clean_waist(self):
        waist = self.cleaned_data.get('waist')
        if waist is not None and waist <= 0:
            raise forms.ValidationError('La cintura debe ser mayor a 0.')
        if waist is not None and waist > 200:
            raise forms.ValidationError('La cintura debe ser menor a 200 cm.')
        return waist
    
    def clean_hip(self):
        hip = self.cleaned_data.get('hip')
        if hip is not None and hip <= 0:
            raise forms.ValidationError('La cadera debe ser mayor a 0.')
        if hip is not None and hip > 200:
            raise forms.ValidationError('La cadera debe ser menor a 200 cm.')
        return hip
    
    def clean_chest(self):
        chest = self.cleaned_data.get('chest')
        if chest is not None and chest <= 0:
            raise forms.ValidationError('El cuello debe ser mayor a 0.')
        if chest is not None and chest > 100:
            raise forms.ValidationError('El cuello debe ser menor a 100 cm.')
        return chest