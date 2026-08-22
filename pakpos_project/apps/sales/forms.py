from django import forms
from .models import DiningTable, Customer


class CustomerForm(forms.ModelForm):
    """
    Form for Creating and Updating Customers in POS Directory & Admin Management.
    """
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'email', 'address', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'id': 'id_customer_name',
                'placeholder': 'e.g. Muhammad Ali, Sheikh Enterprises',
                'required': True
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'id': 'id_customer_phone',
                'placeholder': 'e.g. 03001234567, +92 321 9876543',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'id': 'id_customer_email',
                'placeholder': 'e.g. customer@example.com'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-textarea',
                'id': 'id_customer_address',
                'rows': 3,
                'placeholder': 'House / Shop #, Street, Block, Area, City (for delivery routing)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-textarea',
                'id': 'id_customer_notes',
                'rows': 2,
                'placeholder': 'Special preferences, VIP status, dietary restrictions...'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Customer name is required.")
        return name

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise forms.ValidationError("Phone number is required.")

        qs = Customer.objects.filter(phone__iexact=phone)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(f'A customer with phone number "{phone}" is already registered.')
        return phone


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
