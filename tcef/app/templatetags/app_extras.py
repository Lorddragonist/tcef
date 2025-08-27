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

@register.filter
def month_name_short(month_number):
    """Filtro para obtener el nombre corto del mes"""
    month_names = {
        1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
    }
    return month_names.get(month_number, '') 