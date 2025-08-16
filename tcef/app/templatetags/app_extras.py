from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Filtro personalizado para acceder a elementos de un diccionario por clave"""
    return dictionary.get(key)

@register.filter
def get_item_safe(dictionary, key):
    """Filtro seguro que retorna None si la clave no existe"""
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None 