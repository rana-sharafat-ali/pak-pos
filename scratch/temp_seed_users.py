import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pakpos_project.settings')
import django
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def seed_users():
    # 1. Admin Account
    admin, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@pakpos.com',
            'first_name': 'System',
            'last_name': 'Administrator',
            'role': User.Role.ADMIN,
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
        }
    )
    admin.set_password('admin123')
    admin.role = User.Role.ADMIN
    admin.is_staff = True
    admin.is_superuser = True
    admin.is_active = True
    admin.save()
    print(f"Admin account ready: admin / admin@pakpos.com / admin123 (Role: Admin)")

    # 2. Manager Account
    manager, created = User.objects.get_or_create(
        username='manager',
        defaults={
            'email': 'manager@pakpos.com',
            'first_name': 'Hamza',
            'last_name': 'Manager',
            'role': User.Role.MANAGER,
            'is_staff': False,
            'is_superuser': False,
            'is_active': True,
        }
    )
    manager.set_password('manager123')
    manager.role = User.Role.MANAGER
    manager.is_active = True
    manager.save()
    print(f"Manager account ready: manager / manager@pakpos.com / manager123 (Role: Manager)")

    # 3. Cashier Account
    cashier, created = User.objects.get_or_create(
        username='cashier',
        defaults={
            'email': 'cashier@pakpos.com',
            'first_name': 'Bilal',
            'last_name': 'Cashier',
            'role': User.Role.CASHIER,
            'is_staff': False,
            'is_superuser': False,
            'is_active': True,
        }
    )
    cashier.set_password('cashier123')
    cashier.role = User.Role.CASHIER
    cashier.is_active = True
    cashier.save()
    print(f"Cashier account ready: cashier / cashier@pakpos.com / cashier123 (Role: Cashier)")

    # Update any legacy users with old roles
    User.objects.filter(role='staff').update(role=User.Role.CASHIER)
    User.objects.filter(role='kitchen').update(role=User.Role.CASHIER)

if __name__ == '__main__':
    seed_users()
