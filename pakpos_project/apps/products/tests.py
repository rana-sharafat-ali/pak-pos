from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Product, ProductVariant, Category
from decimal import Decimal

User = get_user_model()


class ProductVariantTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin_test@pakpos.com',
            password='adminpass123',
            role=User.Role.ADMIN
        )
        self.cashier_user = User.objects.create_user(
            username='cashier_prod_test',
            email='cashier_prod_test@pakpos.com',
            password='cashierpass123',
            role=User.Role.CASHIER
        )
        self.client.force_login(self.admin_user)
        self.category = Category.objects.create(name="Pizza", description="Delicious Italian Pizzas")
        
        # 1. Product with sizes / variants (e.g. Pizza)
        self.pizza = Product.objects.create(
            name="Chicken Fajita Pizza",
            category=self.category,
            has_variants=True,
            description="Spicy chicken fajita with capsicum and cheese"
        )
        self.v_small = ProductVariant.objects.create(
            product=self.pizza,
            name="Small",
            cost_price=Decimal("250.00"),
            selling_price=Decimal("500.00"),
            stock_quantity=50
        )
        self.v_med = ProductVariant.objects.create(
            product=self.pizza,
            name="Medium",
            cost_price=Decimal("450.00"),
            selling_price=Decimal("950.00"),
            stock_quantity=30
        )
        self.v_large = ProductVariant.objects.create(
            product=self.pizza,
            name="Large",
            cost_price=Decimal("700.00"),
            selling_price=Decimal("1500.00"),
            stock_quantity=20
        )

        # 2. Simple single price product
        self.drink = Product.objects.create(
            name="Coca Cola 1.5L",
            category=self.category,
            has_variants=False,
            base_price=Decimal("200.00"),
            cost_price=Decimal("160.00"),
            stock_quantity=100
        )

    def test_product_list_view(self):
        response = self.client.get(reverse('products:product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chicken Fajita Pizza")
        self.assertContains(response, "Coca Cola 1.5L")
        self.assertContains(response, "500.00")

    def test_filter_by_type(self):
        # Multi-size filter
        response = self.client.get(reverse('products:product_list'), {'type': 'variants'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chicken Fajita Pizza")
        self.assertNotContains(response, "Coca Cola 1.5L")

        # Single item filter
        response_simple = self.client.get(reverse('products:product_list'), {'type': 'simple'})
        self.assertEqual(response_simple.status_code, 200)
        self.assertContains(response_simple, "Coca Cola 1.5L")
        self.assertNotContains(response_simple, "Chicken Fajita Pizza")

    def test_product_detail_view_with_variants(self):
        response = self.client.get(reverse('products:product_detail', kwargs={'pk': self.pizza.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chicken Fajita Pizza")
        self.assertContains(response, "Small")
        self.assertContains(response, "PKR 500.00")
        self.assertContains(response, "Medium")
        self.assertContains(response, "PKR 950.00")
        self.assertContains(response, "Large")
        self.assertContains(response, "PKR 1500.00")

    def test_product_create_single_item(self):
        post_data = {
            'name': 'Garlic Bread',
            'category': self.category.id,
            'has_variants': '',
            'base_price': '350.00',
            'cost_price': '180.00',
            'stock_quantity': '40',
            'is_active': 'on',
            'variants-TOTAL_FORMS': '0',
            'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
        }
        response = self.client.post(reverse('products:product_create'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(name='Garlic Bread').exists())

    def test_product_create_with_sizes(self):
        post_data = {
            'name': 'Crown Crust Pizza',
            'category': self.category.id,
            'has_variants': 'on',
            'is_active': 'on',
            'variants-TOTAL_FORMS': '2',
            'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            'variants-0-name': 'Medium',
            'variants-0-cost_price': '600.00',
            'variants-0-selling_price': '1200.00',
            'variants-0-is_active': 'on',
            'variants-1-name': 'Large',
            'variants-1-cost_price': '900.00',
            'variants-1-selling_price': '1800.00',
            'variants-1-is_active': 'on',
        }
        response = self.client.post(reverse('products:product_create'), post_data)
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name='Crown Crust Pizza')
        self.assertEqual(product.variants.count(), 2)
        self.assertTrue(product.variants.filter(name='Large', selling_price=Decimal('1800.00')).exists())

    def test_product_delete(self):
        pizza_id = self.pizza.id
        response = self.client.post(reverse('products:product_delete', kwargs={'pk': pizza_id}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=pizza_id).exists())
        # Verify variants were cascade-deleted
        self.assertEqual(ProductVariant.objects.filter(product_id=pizza_id).count(), 0)

    def test_core_dashboard(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total Products")
        self.assertContains(response, "Multi-Size Items (Pizza)")

    def test_category_crud(self):
        # 1. Create Category with Emoji
        create_resp = self.client.post(reverse('products:category_create'), {
            'name': 'Pasta & Italian',
            'icon': '🍝',
            'description': 'Delicious pastas and lasagna',
        })
        self.assertEqual(create_resp.status_code, 302)
        cat = Category.objects.get(name='Pasta & Italian')
        self.assertEqual(cat.icon, '🍝')

        # 2. List Categories
        list_resp = self.client.get(reverse('products:category_list'))
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'Pasta &amp; Italian')
        self.assertTrue(any(c.id == cat.id for c in list_resp.context['categories']))

        # 3. Update Category Emoji
        update_resp = self.client.post(reverse('products:category_update', kwargs={'pk': cat.id}), {
            'name': 'Pasta and Italian Cuisine',
            'icon': '🍜',
            'description': 'Updated description',
        })
        self.assertEqual(update_resp.status_code, 302)
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Pasta and Italian Cuisine')
        self.assertEqual(cat.icon, '🍜')

        # 4. Delete Category
        delete_resp = self.client.post(reverse('products:category_delete', kwargs={'pk': cat.id}))
        self.assertEqual(delete_resp.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=cat.id).exists())

    def test_duplicate_product_prevention(self):
        # 1. Exact Duplicate (Same Name + Same Category + Same Price) should fail
        post_data_dup = {
            'name': 'coca cola 1.5l',
            'category': self.category.id,
            'base_price': '200.00',  # Same price as self.drink
            'cost_price': '160.00',
            'variants-TOTAL_FORMS': '0',
            'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
        }
        response_dup = self.client.post(reverse('products:product_create'), post_data_dup)
        self.assertEqual(response_dup.status_code, 200)
        self.assertTrue('form' in response_dup.context)
        self.assertIn('name', response_dup.context['form'].errors)

        # 2. Same Name with Different Price is allowed
        post_data_diff_price = {
            'name': 'Coca Cola 1.5L',
            'category': self.category.id,
            'base_price': '250.00',  # Different price
            'cost_price': '190.00',
            'variants-TOTAL_FORMS': '0',
            'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
        }
        response_diff = self.client.post(reverse('products:product_create'), post_data_diff_price)
        self.assertEqual(response_diff.status_code, 302)

    def test_duplicate_variant_prevention(self):
        # Attempt to create product with two 'Medium' sizes
        post_data = {
            'name': 'Special BBQ Pizza',
            'category': self.category.id,
            'has_variants': 'on',
            'is_active': 'on',
            'variants-TOTAL_FORMS': '2',
            'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            'variants-0-name': 'Medium',
            'variants-0-cost_price': '500.00',
            'variants-0-selling_price': '1000.00',
            'variants-0-is_active': 'on',
            'variants-1-name': 'medium',  # duplicate
            'variants-1-cost_price': '600.00',
            'variants-1-selling_price': '1100.00',
            'variants-1-is_active': 'on',
        }
        response = self.client.post(reverse('products:product_create'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(name='Special BBQ Pizza').exists())

    def test_product_bulk_delete(self):
        # Create multiple products
        p1 = Product.objects.create(name='Item 1', category=self.category, base_price=Decimal('100.00'))
        p2 = Product.objects.create(name='Item 2', category=self.category, base_price=Decimal('200.00'))
        p3 = Product.objects.create(name='Item 3', category=self.category, base_price=Decimal('300.00'))

        # Bulk delete p1 and p2
        response = self.client.post(reverse('products:product_bulk_delete'), {
            'selected_ids': f'{p1.id},{p2.id}'
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=p1.id).exists())
        self.assertFalse(Product.objects.filter(pk=p2.id).exists())
        self.assertTrue(Product.objects.filter(pk=p3.id).exists())

    def test_category_bulk_delete(self):
        # Create multiple categories
        c1 = Category.objects.create(name='Bulk Cat 1', icon='🥤')
        c2 = Category.objects.create(name='Bulk Cat 2', icon='🍰')
        c3 = Category.objects.create(name='Bulk Cat 3', icon='🍔')

        # Bulk delete c1 and c2
        response = self.client.post(reverse('products:category_bulk_delete'), {
            'selected_ids': f'{c1.id},{c2.id}'
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=c1.id).exists())
        self.assertFalse(Category.objects.filter(pk=c2.id).exists())
        self.assertTrue(Category.objects.filter(pk=c3.id).exists())

    def test_google_sheets_url_conversion(self):
        from .services import convert_google_sheet_url_to_csv_url
        edit_url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing"
        converted = convert_google_sheet_url_to_csv_url(edit_url)
        self.assertIn("/export?format=csv", converted)
        self.assertIn("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms", converted)

    def test_parse_and_import_with_auto_category_creation(self):
        from .services import parse_and_import_products
        csv_data = (
            "Product Name,Category,Selling Price,Sizes,Cost Price,Stock Quantity\n"
            "Super Supreme Pizza,New Fresh Category,0,Small:600 | Large:1800,350,40\n"
            "Chipotle Zinger,Burgers & Sandwiches,550,,300,50\n"
        )
        count, cats_count, errors = parse_and_import_products(csv_data)
        self.assertEqual(count, 2)
        self.assertEqual(cats_count, 2)  # Both 'New Fresh Category' and 'Burgers & Sandwiches' auto-created!
        self.assertEqual(errors, [])
        self.assertTrue(Category.objects.filter(name='New Fresh Category').exists())
        self.assertTrue(Category.objects.filter(name='Burgers & Sandwiches').exists())
        p_pizza = Product.objects.get(name='Super Supreme Pizza')
        self.assertTrue(p_pizza.has_variants)
        self.assertEqual(p_pizza.variants.count(), 2)

    def test_cashier_cannot_access_product_catalog(self):
        """Test Cashier role is restricted from accessing product catalog and redirected to POS"""
        self.client.force_login(self.cashier_user)
        response = self.client.get(reverse('products:product_list'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('sales:pos'))

