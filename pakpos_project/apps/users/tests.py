from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class AuthAndUserManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create Admin
        self.admin = User.objects.create_superuser(
            username='test_admin',
            email='admin@test.com',
            password='adminpassword123',
            first_name='Super',
            last_name='Admin'
        )
        
        # Create Staff
        self.staff = User.objects.create_user(
            username='test_staff',
            email='staff@test.com',
            password='staffpassword123',
            first_name='Normal',
            last_name='Staff'
        )

    def test_case_insensitive_username_login(self):
        """Test login with lowercase, uppercase, and mixed case username"""
        # Lowercase
        response = self.client.post(reverse('users:login'), {
            'username_or_email': 'test_admin',
            'password': 'adminpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:home'))

        self.client.logout()

        # Uppercase
        response = self.client.post(reverse('users:login'), {
            'username_or_email': 'TEST_ADMIN',
            'password': 'adminpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:home'))

    def test_case_insensitive_email_login(self):
        """Test login with lowercase and UPPERCASE email"""
        response = self.client.post(reverse('users:login'), {
            'username_or_email': 'ADMIN@TEST.COM',
            'password': 'adminpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:home'))

    def test_whitespace_trimmed_login(self):
        """Test login with leading and trailing spaces"""
        response = self.client.post(reverse('users:login'), {
            'username_or_email': '  staff@test.com  ',
            'password': 'staffpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('sales:pos'))

    def test_staff_role_redirect_to_products(self):
        """Test that Staff login redirects directly to POS Terminal"""
        response = self.client.post(reverse('users:login'), {
            'username_or_email': 'test_staff',
            'password': 'staffpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('sales:pos'))

    def test_staff_cannot_access_user_management(self):
        """Test that Staff is blocked from accessing Admin User Management page"""
        self.client.force_login(self.staff)
        response = self.client.get(reverse('users:user_list'))
        # Should redirect to cashier home (POS)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('sales:pos'))

    def test_admin_can_access_user_management(self):
        """Test that Admin can access User Management page"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('users:user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Team & Operator Management')

    def test_admin_reset_staff_password(self):
        """Test that Admin can directly change a staff member's password"""
        self.client.force_login(self.admin)
        response = self.client.post(reverse('users:user_reset_password', kwargs={'pk': self.staff.pk}), {
            'new_password': 'brandnewpassword123',
            'confirm_password': 'brandnewpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.client.logout()

        # Staff can now login with new password
        login_resp = self.client.post(reverse('users:login'), {
            'username_or_email': 'test_staff',
            'password': 'brandnewpassword123'
        })
        self.assertEqual(login_resp.status_code, 302)

    def test_admin_change_own_password(self):
        """Test Admin changing own password verifying current password"""
        self.client.force_login(self.admin)
        response = self.client.post(reverse('users:change_own_password'), {
            'current_password': 'adminpassword123',
            'new_password': 'supersecretpass789',
            'confirm_password': 'supersecretpass789'
        })
        self.assertEqual(response.status_code, 302)
        self.client.logout()

        # Login with new password
        login_resp = self.client.post(reverse('users:login'), {
            'username_or_email': 'test_admin',
            'password': 'supersecretpass789'
        })
        self.assertEqual(login_resp.status_code, 302)

    def test_self_deactivation_blocked(self):
        """Test Admin cannot deactivate their own account"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('users:user_toggle_status', kwargs={'pk': self.admin.pk}))
        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_deactivated_user_login_blocked(self):
        """Test that deactivated users cannot log in"""
        self.staff.is_active = False
        self.staff.save()

        response = self.client.post(reverse('users:login'), {
            'username_or_email': 'test_staff',
            'password': 'staffpassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'deactivated')
