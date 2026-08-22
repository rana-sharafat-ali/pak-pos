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
        self.assertContains(response, 'Executive Analytics')
        self.assertContains(response, 'Total Sales Inflow')
        self.assertContains(response, 'Net Profit')

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

    def test_download_db_backup_admin(self):
        self.client.login(username='admin_settings', password='adminpass123')
        response = self.client.get(reverse('core:download_db_backup'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/x-sqlite3')
        self.assertTrue('attachment; filename="pakpos_db_backup_' in response['Content-Disposition'])

    def test_download_json_backup_admin(self):
        self.client.login(username='admin_settings', password='adminpass123')
        response = self.client.get(reverse('core:download_json_backup'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertTrue('attachment; filename="pakpos_data_dump_' in response['Content-Disposition'])

    def test_restore_db_cashier_forbidden(self):
        self.client.login(username='cashier_settings', password='cashierpass123')
        response = self.client.post(reverse('core:restore_db'))
        # Cashier must be redirected (forbidden from restoring DB)
        self.assertEqual(response.status_code, 302)

    def test_restore_db_invalid_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.login(username='admin_settings', password='adminpass123')
        bad_file = SimpleUploadedFile("bad_file.txt", b"invalid content", content_type="text/plain")
        response = self.client.post(reverse('core:restore_db'), {'backup_file': bad_file}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid file format')

    def test_rollback_cashier_forbidden(self):
        self.client.login(username='cashier_settings', password='cashierpass123')
        response = self.client.post(reverse('core:rollback_db'))
        self.assertEqual(response.status_code, 302)

    def test_rollback_no_state(self):
        self.client.login(username='admin_settings', password='adminpass123')
        response = self.client.post(reverse('core:rollback_db'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rollback is no longer available')

    def test_extract_gdrive_folder_id(self):
        from pakpos_project.apps.core.views import extract_gdrive_folder_id
        url = "https://drive.google.com/drive/folders/1abc987XYZ-folder_id?usp=sharing"
        self.assertEqual(extract_gdrive_folder_id(url), "1abc987XYZ-folder_id")
        self.assertEqual(extract_gdrive_folder_id("raw_folder_id_123"), "raw_folder_id_123")

    def test_gdrive_upload_api_anonymous_forbidden(self):
        # Unauthenticated users must be redirected
        response = self.client.post(reverse('core:gdrive_backup_upload'))
        self.assertEqual(response.status_code, 302)

    def test_gdrive_upload_api_remote_not_allowed(self):
        self.client.login(username='admin_settings', password='adminpass123')
        from pakpos_project.apps.core.models import SystemSetting
        settings = SystemSetting.load()
        settings.gdrive_remote_active = False
        settings.save()

        response = self.client.post(reverse('core:gdrive_backup_upload'))
        self.assertEqual(response.status_code, 403)
        self.assertIn('not allowed', response.json().get('error', '').lower())
