from django import template
from django.utils.safestring import mark_safe
from django.utils.timezone import now

from datetime import timedelta, datetime

register = template.Library()

@register.filter(name='past')
def past(date):
    return now() > date if date else False

@register.filter(name='orcross', is_safe=True)
def orcross(value):
    if value:
        return value
    else:
        return mark_safe('<div class="text-left"><i class="icon icon-cross"></i></div>')


@register.filter(name='orcheck', is_safe=True)
def orcheck(value):
    if value:
        return value
    else:
        return mark_safe('<div class="text-left"><i class="icon icon-check"></i></div>')


@register.filter(name='oredit', is_safe=True)
def oredit(value, url):
    if value:
        return value
    else:
        return mark_safe('<div class="text-left"><a href="{}" class="icon icon-edit"></a></div>'.format(url))

@register.filter(name='checkorcross', is_safe=True)
def checkorcross(value):
    if value:
        return mark_safe('<div class="text-left"><i class="icon icon-check"></i></div>')
    else:
        return mark_safe('<div class="text-left"><i class="icon icon-cross"></i></div>')
