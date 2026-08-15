from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class LoginForm(forms.Form):
    """
    Dual Login Form supporting Username or Email authentication with Remember Me option
    """
    username_or_email = forms.CharField(
        label='Email Address',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'field-input',
            'placeholder': 'name@company.com',
            'autocomplete': 'username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
            'id': 'password-field-input',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'id': 'remember-me-checkbox',
        })
    )

    def clean_username_or_email(self):
        val = self.cleaned_data.get('username_or_email', '')
        return val.strip() if val else ''


class AdminUserCreationForm(forms.ModelForm):
    """
    Admin-only form to register new Staff / Manager / Admin members
    """
    password = forms.CharField(
        label='Temporary / Initial Password',
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'placeholder': 'Minimum 6 characters',
        })
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'placeholder': 'Re-enter password',
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'phone_number']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'e.g. cashier_ali'}),
            'email': forms.EmailInput(attrs={'class': 'field-input', 'placeholder': 'e.g. ali@pakpos.com'}),
            'first_name': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Last Name'}),
            'role': forms.Select(attrs={'class': 'field-input select-filter'}),
            'phone_number': forms.TextInput(attrs={'class': 'field-input', 'placeholder': '+92 300 1234567'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError('Username is required.')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('A user with this username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise ValidationError('Email address is required.')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('A user with this email address already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')

        if password and len(password) < 6:
            self.add_error('password', 'Password must be at least 6 characters long.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        user.set_password(password)
        user.is_active = True
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    """
    Admin form to update operator profile, role, and active status
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'role', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'field-input'}),
            'last_name': forms.TextInput(attrs={'class': 'field-input'}),
            'email': forms.EmailInput(attrs={'class': 'field-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'field-input'}),
            'role': forms.Select(attrs={'class': 'field-input select-filter'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, requesting_user=None, **kwargs):
        self.requesting_user = requesting_user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise ValidationError('Email address is required.')
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('A user with this email address already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        is_active = cleaned_data.get('is_active')

        # Safeguard: Prevent last active admin from being deactivated or demoted
        if self.instance and self.instance.role == User.Role.ADMIN:
            if not is_active or role != User.Role.ADMIN:
                active_admins = User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=self.instance.pk)
                if not active_admins.exists():
                    raise ValidationError('Cannot deactivate or demote the only remaining active Administrator in the system.')

        return cleaned_data


class AdminResetUserPasswordForm(forms.Form):
    """
    Form allowing Admin to directly set a new password for a Staff member
    """
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'placeholder': 'Minimum 6 characters',
        })
    )
    confirm_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'placeholder': 'Re-enter new password',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')

        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Passwords do not match.')

        if p1 and len(p1) < 6:
            self.add_error('new_password', 'Password must be at least 6 characters long.')

        return cleaned_data


class ChangeOwnPasswordForm(forms.Form):
    """
    Form allowing logged-in user to change their own password by verifying current password
    """
    current_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'placeholder': 'Enter your current password',
        })
    )
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'placeholder': 'Minimum 6 characters',
        })
    )
    confirm_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'field-input',
            'placeholder': 'Re-enter new password',
        })
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        curr = self.cleaned_data.get('current_password')
        if self.user and not self.user.check_password(curr):
            raise ValidationError('Incorrect current password.')
        return curr

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')

        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'New passwords do not match.')

        if p1 and len(p1) < 6:
            self.add_error('new_password', 'New password must be at least 6 characters long.')

        return cleaned_data
