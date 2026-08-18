from django import forms
from .models import DiningTable


class DiningTableForm(forms.ModelForm):
    """
    Form for Creating and Updating Dining Tables in POS Dine-in operations.
    """
    class Meta:
        model = DiningTable
        fields = ['name', 'floor_section', 'capacity', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'id': 'id_table_name',
                'placeholder': 'e.g. Table 1, Table 2, VIP 1, Outdoor 1',
                'required': True
            }),
            'floor_section': forms.TextInput(attrs={
                'class': 'form-input',
                'id': 'id_floor_section',
                'placeholder': 'e.g. Main Hall, Ground Floor, Rooftop, VIP Lounge, Lawn'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-input',
                'id': 'id_table_capacity',
                'min': '1',
                'max': '100',
                'placeholder': '4'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Optional table notes or specific location details...'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Table name is required.")

        qs = DiningTable.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(f'A dining table named "{name}" already exists. Please choose a different table name.')
        return name

    def clean_capacity(self):
        cap = self.cleaned_data.get('capacity')
        if cap is None or cap < 1:
            raise forms.ValidationError("Seating capacity must be at least 1.")
        return cap
