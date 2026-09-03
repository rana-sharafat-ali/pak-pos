from django import template
from django.db.models import Sum

register = template.Library()

@register.simple_tag
def get_shift_expenses(shift):
    total = shift.expenses.aggregate(total=Sum('amount'))['total']
    return total or 0
