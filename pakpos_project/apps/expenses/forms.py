from django import forms
from .models import Expense, ExpenseCategory

class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'e.g. Utilities, Salaries'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'custom-checkbox'})
        }

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'category', 'amount', 'description']
        widgets = {
            'date': forms.DateTimeInput(attrs={'class': 'field-input', 'type': 'datetime-local'}),
            'category': forms.Select(attrs={'class': 'field-input select-filter'}),
            'amount': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'field-input', 'rows': 3, 'placeholder': 'Details about the expense...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
