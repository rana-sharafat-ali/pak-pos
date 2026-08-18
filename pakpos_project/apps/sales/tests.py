import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from pakpos_project.apps.products.models import Product, ProductVariant, Category
from .models import Customer, Sale, SaleItem, CashDrawerShift, DiningTable
from .forms import DiningTableForm

User = get_user_model()


class SalesAndPOSTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Cashier User
        self.cashier = User.objects.create_user(
            username='cashier_test',
            email='cashier_test@pakpos.com',
            password='cashierpass123',
            role=User.Role.CASHIER
        )

        # Create Manager User
        self.manager = User.objects.create_user(
            username='manager_test',
            email='manager_test@pakpos.com',
            password='managerpass123',
            role=User.Role.MANAGER
        )


        # Create Category
        self.category = Category.objects.create(name='Fast Food', icon='🍔')

        # Create Standard Product with Stock
        self.standard_product = Product.objects.create(
            name='Crispy Zinger Burger',
            category=self.category,
            base_price=Decimal('550.00'),
            cost_price=Decimal('350.00'),
            stock_quantity=50,
            track_stock=True
        )

        # Create Variant Product with Sizes
        self.variant_product = Product.objects.create(
            name='Chicken Tikka Pizza',
            category=self.category,
            has_variants=True
        )
        self.size_small = ProductVariant.objects.create(
            product=self.variant_product,
            name='Small',
            cost_price=Decimal('400.00'),
            selling_price=Decimal('650.00'),
            stock_quantity=20
        )
        self.size_large = ProductVariant.objects.create(
            product=self.variant_product,
            name='Large',
            cost_price=Decimal('800.00'),
            selling_price=Decimal('1400.00'),
            stock_quantity=15
        )

    def test_pos_terminal_view_renders(self):
        """Test POS terminal page loads successfully with catalog JSON and barcodes for cashier"""
        self.client.force_login(self.cashier)
        response = self.client.get(reverse('sales:pos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Point of Sale (POS)')
        self.assertContains(response, 'Crispy Zinger Burger')
        # Verify barcodes are present in the JSON payload
        self.assertContains(response, f"800{self.standard_product.id:03d}00")
        self.assertContains(response, f"800{self.variant_product.id:03d}{self.size_large.id:02d}")


    def test_checkout_sale_creation_and_stock_deduction(self):
        """
        Test completing an order via api_checkout:
        Verifies:
        - Sale & SaleItem records created
        - Sequential invoice number generated (INV-YYYYMMDD-XXXX)
        - Subtotal, discount, tax, service charges, total & change calculated
        - Stock deducted for both standard and variant products
        """
        self.client.force_login(self.cashier)

        payload = {
            'customer_name': 'Ali Khan',
            'customer_phone': '03001234567',
            'customer_email': 'ali@example.com',
            'customer_address': 'House 12, Street 4, Lahore',
            'payment_method': 'cash',
            'amount_tendered': 3000.00,
            'discount_type': 'fixed',
            'discount_value': 100.00,
            'tax_rate': 0.0,
            'service_charge_rate': 0.0,
            'notes': 'Table 5 Order',
            'items': [
                {
                    'product_id': self.standard_product.id,
                    'variant_id': None,
                    'quantity': 2,  # 550 * 2 = 1100
                },
                {
                    'product_id': self.variant_product.id,
                    'variant_id': self.size_large.id,
                    'quantity': 1,  # 1400 * 1 = 1400
                }
            ]
        }

        # Subtotal: 1100 + 1400 = 2500
        # Discount: 100
        # Net Total: 2400
        # Tendered: 3000 -> Change: 600

        response = self.client.post(
            reverse('sales:api_checkout'),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_amount'], 2400.0)
        self.assertEqual(data['change_returned'], 600.0)

        # Verify Database Sale Record
        sale = Sale.objects.get(id=data['sale_id'])
        self.assertTrue(sale.invoice_number.startswith('INV-'))
        self.assertEqual(sale.subtotal, Decimal('2500.00'))
        self.assertEqual(sale.discount_amount, Decimal('100.00'))
        self.assertEqual(sale.total_amount, Decimal('2400.00'))
        self.assertEqual(sale.amount_tendered, Decimal('3000.00'))
        self.assertEqual(sale.change_returned, Decimal('600.00'))
        self.assertEqual(sale.customer.phone, '03001234567')
        self.assertEqual(sale.customer.name, 'Ali Khan')
        self.assertEqual(sale.items.count(), 2)

        # Verify Automatic Stock Deduction
        self.standard_product.refresh_from_db()
        self.assertEqual(self.standard_product.stock_quantity, 48)  # 50 - 2

        self.size_large.refresh_from_db()
        self.assertEqual(self.size_large.stock_quantity, 14)  # 15 - 1

    def test_sale_refund_and_inventory_restock_rollback(self):
        """
        Test processing a refund for a sale:
        Verifies:
        - Sale status changes to REFUNDED
        - Items inventory is restored/rolled back automatically
        """
        self.client.force_login(self.cashier)

        # Create Sale
        sale = Sale.objects.create(
            cashier=self.cashier,
            subtotal=Decimal('1100.00'),
            total_amount=Decimal('1100.00'),
            payment_method=Sale.PaymentMethod.CASH,
            amount_tendered=Decimal('1100.00')
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.standard_product,
            product_name=self.standard_product.name,
            unit_price=Decimal('550.00'),
            quantity=2,
            total_price=Decimal('1100.00')
        )
        # Deduct initial stock
        self.standard_product.stock_quantity = 48
        self.standard_product.save()

        # Cashier cannot refund
        self.client.force_login(self.cashier)
        cashier_refund = self.client.post(
            reverse('sales:refund', kwargs={'pk': sale.pk}),
            {'refund_reason': 'Customer returned items'}
        )
        self.assertEqual(cashier_refund.status_code, 302)

        # Manager performs refund
        self.client.force_login(self.manager)
        refund_resp = self.client.post(
            reverse('sales:refund', kwargs={'pk': sale.pk}),
            {'refund_reason': 'Customer returned items'}
        )
        self.assertEqual(refund_resp.status_code, 302)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.REFUNDED)
        self.assertEqual(sale.refund_reason, 'Customer returned items')
        self.assertIsNotNone(sale.refunded_at)

        # Verify Stock was Rolled Back / Restocked
        self.standard_product.refresh_from_db()
        self.assertEqual(self.standard_product.stock_quantity, 50)  # 48 + 2

    def test_customer_search_autocomplete(self):
        """Test API autocomplete searching customers by phone or name"""
        Customer.objects.create(name='Usman Tariq', phone='03219876543')
        self.client.force_login(self.cashier)

        response = self.client.get(reverse('sales:api_customer_search'), {'q': '0321'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['customers']), 1)
        self.assertEqual(data['customers'][0]['name'], 'Usman Tariq')

    def test_thermal_receipt_and_invoice_views(self):
        """Test rendering of thermal receipt and A4 invoice"""
        self.client.force_login(self.cashier)

        sale = Sale.objects.create(
            cashier=self.cashier,
            subtotal=Decimal('550.00'),
            total_amount=Decimal('550.00')
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.standard_product,
            product_name=self.standard_product.name,
            unit_price=Decimal('550.00'),
            quantity=1,
            total_price=Decimal('550.00')
        )

        receipt_resp = self.client.get(reverse('sales:receipt', kwargs={'pk': sale.pk}))
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertContains(receipt_resp, sale.invoice_number)

        invoice_resp = self.client.get(reverse('sales:invoice_a4', kwargs={'pk': sale.pk}))
        self.assertEqual(invoice_resp.status_code, 200)
        self.assertContains(invoice_resp, 'TAX INVOICE')

    def test_sales_ledger_and_shift_summary(self):
        """Test sales history ledger table and daily shift reconciliation views including profit and role restrictions"""
        sale = Sale.objects.create(
            cashier=self.cashier,
            subtotal=Decimal('1000.00'),
            total_amount=Decimal('1000.00'),
            payment_method=Sale.PaymentMethod.CASH
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.standard_product,
            product_name=self.standard_product.name,
            cost_price=Decimal('350.00'),
            unit_price=Decimal('500.00'),
            quantity=2,
            total_price=Decimal('1000.00')
        )

        # 1. Cashier is restricted from Sales Ledger
        self.client.force_login(self.cashier)
        cashier_ledger_resp = self.client.get(reverse('sales:ledger'))
        self.assertEqual(cashier_ledger_resp.status_code, 302)
        self.assertRedirects(cashier_ledger_resp, reverse('sales:pos'))

        # 2. Cashier CAN view Daily Shift Summary
        shift_resp = self.client.get(reverse('sales:shift_summary'))
        self.assertEqual(shift_resp.status_code, 200)
        self.assertContains(shift_resp, 'Daily Shift & Cash Drawer Reconciliation')
        self.assertNotContains(shift_resp, 'Net Profit (Today)')  # Profit hidden from cashier

        # 3. Manager CAN view Sales Ledger & Shift Summary & Profit
        self.client.force_login(self.manager)
        shift_mgr_resp = self.client.get(reverse('sales:shift_summary'))
        self.assertEqual(shift_mgr_resp.status_code, 200)
        self.assertContains(shift_mgr_resp, 'Net Profit (Today)')

        # 4. Shift Print standalone printable page test
        shift_print_resp = self.client.get(reverse('sales:shift_print'))
        self.assertEqual(shift_print_resp.status_code, 200)
        self.assertContains(shift_print_resp, 'Daily Shift & Cash Drawer Reconciliation')
        self.assertContains(shift_print_resp, 'Gross Sales')

        # 5. Manager views ledger and net profit before refund
        self.client.force_login(self.manager)
        ledger_resp = self.client.get(reverse('sales:ledger'))
        self.assertEqual(ledger_resp.status_code, 200)
        self.assertContains(ledger_resp, 'Sales & Order Invoices')
        self.assertContains(ledger_resp, 'Net Profit')
        self.assertContains(ledger_resp, '300.00')  # 1000 revenue - 700 cost = 300 profit

        # 6. Cashier CAN process refund from shift
        self.client.force_login(self.cashier)
        refund_resp = self.client.post(reverse('sales:refund', args=[sale.id]), {'refund_reason': 'Customer requested refund'})
        self.assertEqual(refund_resp.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.REFUNDED)

    def test_subtotal_gst_service_discount_calculation_order(self):
        """
        Verify the financial calculation formula:
        Total Payable = (Subtotal + GST + Service Charges) - Discount
        Tax and Service Charges are calculated on Subtotal, and discount is subtracted from the gross total.
        """
        self.client.force_login(self.cashier)

        # 2 x Large Pizza @ 1400 = 2800 subtotal
        # Tax: 5% of 2800 = 140
        # Service Charge: 10% of 2800 = 280
        # Gross Total: 2800 + 140 + 280 = 3220
        # Discount: 220
        # Net Total: 3220 - 220 = 3000
        payload = {
            'customer_name': 'Hassan Raza',
            'customer_phone': '03119876543',
            'payment_method': 'cash',
            'order_type': 'dine_in',
            'tax_rate': 5.0,
            'service_charge_rate': 10.0,
            'discount_type': 'fixed',
            'discount_value': 220.0,
            'amount_tendered': 3000.0,
            'items': [
                {
                    'product_id': self.variant_product.id,
                    'variant_id': self.size_large.id,
                    'quantity': 2,
                }
            ]
        }

        response = self.client.post(
            reverse('sales:api_checkout'),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_amount'], 3000.0)
        self.assertEqual(data['change_returned'], 0.0)

        sale = Sale.objects.get(id=data['sale_id'])
        self.assertEqual(sale.subtotal, Decimal('2800.00'))
        self.assertEqual(sale.tax_amount, Decimal('140.00'))
        self.assertEqual(sale.service_charge_amount, Decimal('280.00'))
        self.assertEqual(sale.discount_amount, Decimal('220.00'))
        self.assertEqual(sale.total_amount, Decimal('3000.00'))


class DiningTableCRUDTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_tables',
            email='admin_tables@pakpos.com',
            password='adminpass123',
            role=User.Role.ADMIN
        )
        self.cashier = User.objects.create_user(
            username='cashier_tables',
            email='cashier_tables@pakpos.com',
            password='cashierpass123',
            role=User.Role.CASHIER
        )
        self.table = DiningTable.objects.create(
            name='Table 101',
            floor_section='Rooftop',
            capacity=6,
            status=DiningTable.Status.AVAILABLE,
            is_active=True,
            notes='Corner table with view'
        )

    def test_dining_table_model_str(self):
        self.assertIn('Table 101', str(self.table))
        self.assertIn('Rooftop', str(self.table))

    def test_table_list_view_authenticated(self):
        self.client.login(username='admin_tables', password='adminpass123')
        response = self.client.get(reverse('sales:table_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Table 101')
        self.assertContains(response, 'Rooftop')

    def test_table_list_view_search(self):
        self.client.login(username='admin_tables', password='adminpass123')
        response = self.client.get(reverse('sales:table_list') + '?q=Corner')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Table 101')

    def test_table_create_view_post(self):
        self.client.login(username='admin_tables', password='adminpass123')
        response = self.client.post(reverse('sales:table_create'), {
            'name': 'VIP Rooftop 5',
            'floor_section': 'VIP Lounge',
            'capacity': 8,
            'is_active': True,
            'notes': 'Special reservations only'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(DiningTable.objects.filter(name='VIP Rooftop 5').exists())

    def test_table_create_duplicate_rejected(self):
        self.client.login(username='admin_tables', password='adminpass123')
        response = self.client.post(reverse('sales:table_create'), {
            'name': 'Table 101',
            'floor_section': 'Main Hall',
            'capacity': 4,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'name', 'A dining table named "Table 101" already exists. Please choose a different table name.')

    def test_table_update_view(self):
        self.client.login(username='admin_tables', password='adminpass123')
        response = self.client.post(reverse('sales:table_update', kwargs={'pk': self.table.id}), {
            'name': 'Table 101 Renovated',
            'floor_section': 'Executive Lounge',
            'capacity': 10,
            'is_active': True,
            'notes': 'Updated seating'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.table.refresh_from_db()
        self.assertEqual(self.table.name, 'Table 101 Renovated')
        self.assertEqual(self.table.capacity, 10)

    def test_table_delete_view(self):
        self.client.login(username='admin_tables', password='adminpass123')
        table_id = self.table.id
        response = self.client.post(reverse('sales:table_delete', kwargs={'pk': table_id}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DiningTable.objects.filter(id=table_id).exists())

    def test_table_bulk_delete_view(self):
        self.client.login(username='admin_tables', password='adminpass123')
        t1 = DiningTable.objects.create(name='Bulk Table 1', floor_section='Main Hall', capacity=4)
        t2 = DiningTable.objects.create(name='Bulk Table 2', floor_section='Main Hall', capacity=6)
        response = self.client.post(reverse('sales:table_bulk_delete'), {
            'selected_ids': [str(t1.id), str(t2.id)]
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DiningTable.objects.filter(id=t1.id).exists())
        self.assertFalse(DiningTable.objects.filter(id=t2.id).exists())

    def test_cashier_access_restricted_from_table_crud(self):
        self.client.login(username='cashier_tables', password='cashierpass123')
        response = self.client.get(reverse('sales:table_list'))
        # Cashiers should be redirected (forbidden from admin CRUD)
        self.assertEqual(response.status_code, 302)



