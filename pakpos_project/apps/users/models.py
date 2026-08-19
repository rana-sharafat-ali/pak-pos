from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.exceptions import ValidationError


class UserManager(BaseUserManager):
    """
    Custom user manager supporting case-insensitive lookups and normalization
    """
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field is required.')
        if not email:
            raise ValueError('The Email field is required.')
            
        email = self.normalize_email(email).lower()
        username = username.strip()
        
        extra_fields.setdefault('role', User.Role.CASHIER)
        extra_fields.setdefault('is_active', True)
        
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom Scalable User Model with Role-Based Permissions & Dynamic Routing
    """
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        CASHIER = 'cashier', 'Cashier'

    # Route mapping for post-login destination by role
    ROLE_REDIRECT_MAP = {
        Role.ADMIN: 'core:home',
        Role.CASHIER: 'sales:pos',
    }

    email = models.EmailField(unique=True, max_length=255, verbose_name='Email Address')
    role = models.CharField(
        max_length=20, 
        choices=Role.choices, 
        default=Role.CASHIER,
        verbose_name='User Role'
    )
    phone_number = models.CharField(max_length=25, blank=True, null=True, verbose_name='Phone Number')
    is_synced = models.BooleanField(default=False)

    objects = UserManager()

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
            # Case-insensitive uniqueness check
            duplicate_email = User.objects.filter(email__iexact=self.email).exclude(pk=self.pk)
            if duplicate_email.exists():
                raise ValidationError({'email': 'A user with this email address already exists.'})
                
        if self.username:
            self.username = self.username.strip()
            # Case-insensitive uniqueness check
            duplicate_user = User.objects.filter(username__iexact=self.username).exclude(pk=self.pk)
            if duplicate_user.exists():
                raise ValidationError({'username': 'A user with this username already exists.'})

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if self.username:
            self.username = self.username.strip()
            
        # Keep Django is_staff flag in sync for Admin/Superusers
        if self.role == self.Role.ADMIN or self.is_superuser:
            self.is_staff = True
            
        super().save(*args, **kwargs)

    # Capability and Role Helper Methods
    def has_role(self, *allowed_roles):
        """Check if user has any of the specified roles or is superuser"""
        if self.is_superuser:
            return True
        return self.role in allowed_roles

    @property
    def is_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_manager_or_above(self):
        return self.is_admin

    @property
    def is_cashier(self):
        return self.role == self.Role.CASHIER

    @property
    def can_manage_users(self):
        return self.is_admin

    @property
    def can_manage_catalog(self):
        return self.is_admin

    @property
    def role_display_badge(self):
        badges = {
            self.Role.ADMIN: 'badge-admin',
            self.Role.CASHIER: 'badge-cashier',
        }
        return badges.get(self.role, 'badge-cashier')

    def get_redirect_url(self):
        """Returns the home redirect route name for this user's role"""
        return self.ROLE_REDIRECT_MAP.get(self.role, 'core:home')

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
