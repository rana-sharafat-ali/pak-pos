from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemSettingsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_settings',
            email='admin_settings@pakpos.com',
            password='adminpass123',
            role=User.Role.ADMIN
        )
        self.cashier = User.objects.create_user(
            username='cashier_settings',
            email='cashier_settings@pakpos.com',
            password='cashierpass123',
            role=User.Role.CASHIER
        )

    def test_settings_view_admin_access(self):
        self.client.login(username='admin_settings', password='adminpass123')
        response = self.client.get(reverse('core:system_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'System Settings')
        self.assertContains(response, 'Brand Identity')

    def test_settings_view_cashier_forbidden(self):
        self.client.login(username='cashier_settings', password='cashierpass123')
        response = self.client.get(reverse('core:system_settings'))
        # Cashiers must be redirected (forbidden)
        self.assertEqual(response.status_code, 302)

    def test_settings_save_post(self):
        self.client.login(username='admin_settings', password='adminpass123')
        payload = {
            'app_name': 'PakPOS Pro Store',
            'app_subtitle': 'Multi-Branch POS',
            'app_currency': 'PKR',
            'app_footer_text': 'Thank you for shopping with us!',
            'time_zone': 'Asia/Karachi',
            'pos_operation_mode': 'restaurant',
            'pos_default_tax_percent': 5.0,
            'pos_default_service_charge_percent': 10.0,
            'pos_default_discount_percent': 0.0,
            'pos_auto_apply_discount': False,
            'pos_default_delivery_charges': 150.0,
            'pos_shift_start_hour': 9,
            'pos_shift_end_hour': 23,
            'products_per_page': 50,
            'session_cookie_age_days': 30,
        }
        response = self.client.post(reverse('core:system_settings'), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'System &amp; POS settings updated successfully!')

    def test_dashboard_admin_access_and_presets(self):
        self.client.login(username='admin_settings', password='adminpass123')
        # Default today
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Executive Dashboard')
        self.assertContains(response, 'Total Net Revenue')
        self.assertContains(response, 'Net Gross Profit')

        # Test presets
        for preset in ['today', 'yesterday', 'this_week', 'this_month', 'last_30_days', 'this_year', 'all_time']:
            resp = self.client.get(reverse('core:home'), {'preset': preset})
            self.assertEqual(resp.status_code, 200)

    def test_dashboard_cashier_redirected(self):
        self.client.login(username='cashier_settings', password='cashierpass123')
        response = self.client.get(reverse('core:home'))
        # Cashier must be redirected to POS
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('sales:pos'))
