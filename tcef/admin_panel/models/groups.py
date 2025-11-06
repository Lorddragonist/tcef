from django.db import models
from django.contrib.auth.models import User


class UserGroup(models.Model):
    """Grupo de usuarios para personalizar rutinas"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text='Color del grupo en formato HEX')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Grupo de Usuarios'
        verbose_name_plural = 'Grupos de Usuarios'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_member_count(self):
        return self.members.count()


class UserGroupMembership(models.Model):
    """Relación entre usuarios y grupos - Un usuario solo puede estar en un grupo"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='group_membership')
    group = models.ForeignKey(UserGroup, on_delete=models.CASCADE, related_name='members')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Membresía de Grupo'
        verbose_name_plural = 'Membresías de Grupos'

    def __str__(self):
        return f"{self.user.username} - {self.group.name}"

