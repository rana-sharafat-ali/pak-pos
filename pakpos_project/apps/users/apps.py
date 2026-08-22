from django.apps import AppConfig
from django.db.models.signals import post_migrate


def seed_default_users(sender, **kwargs):
    try:
        from pakpos_project.apps.users.models import User
        
        # Ensure Admin user exists
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@pakpos.local',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            
        # Ensure Cashier user exists
        cashier, created = User.objects.get_or_create(
            username='cashier',
            defaults={
                'email': 'cashier@pakpos.local',
                'role': User.Role.CASHIER,
                'is_staff': False,
                'is_superuser': False,
                'is_active': True
            }
        )
        if created:
            cashier.set_password('cashier123')
            cashier.save()
    except Exception:
        pass


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pakpos_project.apps.users'

    def ready(self):
        post_migrate.connect(seed_default_users, sender=self)
