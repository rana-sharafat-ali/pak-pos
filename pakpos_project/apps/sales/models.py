from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid


class Customer(models.Model):
    """
    Customer Directory & Ledger model for repeat buyers and walk-ins
    """
    name = models.CharField(max_length=150, verbose_name="Customer Name")
    phone = models.CharField(max_length=30, unique=True, db_index=True, verbose_name="Phone Number")
    email = models.EmailField(blank=True, null=True, verbose_name="Email Address")
    address = models.TextField(blank=True, null=True, verbose_name="Delivery / Postal Address")
    notes = models.TextField(blank=True, null=True, verbose_name="Customer Notes / Preferences")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @property
    def total_orders_count(self):
        return self.sales.filter(status=Sale.Status.COMPLETED).count()

    @property
    def total_spent_amount(self):
        total = self.sales.filter(status=Sale.Status.COMPLETED).aggregate(models.Sum('total_amount'))['total_amount__sum']
        return total or Decimal('0.00')


class Sale(models.Model):
    """
    Core POS Sale / Invoice Model representing a completed or parked checkout transaction
    """
    class Status(models.TextChoices):
        COMPLETED = 'completed', 'Completed'
        HELD = 'held', 'Held / Parked'
        REFUNDED = 'refunded', 'Refunded / Returned'
        CANCELLED = 'cancelled', 'Cancelled'

    class OrderType(models.TextChoices):
        WALK_IN = 'walk_in', 'Walk-in'
        DINE_IN = 'dine_in', 'Dine-in'
        TAKEAWAY = 'takeaway', 'Takeaway'
        DELIVERY = 'delivery', 'Delivery'

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card'
        ONLINE = 'online', 'Online'

    class DiscountType(models.TextChoices):
        NONE = 'none', 'None'
        FIXED = 'fixed', 'Fixed Amount (PKR)'
        PERCENTAGE = 'percentage', 'Percentage (%)'

    invoice_number = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="Invoice Number")
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sales', 
        verbose_name="Customer"
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='sales', 
        verbose_name="Cashier / Operator"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED, db_index=True)
    order_type = models.CharField(max_length=20, choices=OrderType.choices, default=OrderType.WALK_IN)
    
    # Financial Calculation Fields
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Subtotal (PKR)")
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.NONE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Discount (PKR)")
    
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Tax Rate (%)")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Tax (PKR)")
    
    service_charge_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Service Charge (%)")
    service_charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Service Charges (PKR)")
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Net Amount (PKR)")
    
    # Payment Processing
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    amount_tendered = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Cash Received (PKR)")
    change_returned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Change Returned (PKR)")
    
    coupon_code = models.CharField(max_length=50, blank=True, null=True, verbose_name="Coupon / Promo Code")
    notes = models.TextField(blank=True, null=True, verbose_name="Order / Billing Notes")
    
    # Returns & Refunds
    refund_reason = models.TextField(blank=True, null=True, verbose_name="Refund Reason")
    refunded_at = models.DateTimeField(blank=True, null=True, verbose_name="Refund Timestamp")
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds_processed',
        verbose_name="Refund Processed By"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sale Invoice"
        verbose_name_plural = "Sales Invoices"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.invoice_number} - PKR {self.total_amount} ({self.get_status_display()})"

    @classmethod
    def generate_invoice_number(cls):
        """
        Generates clean chronological sequential invoice numbers (e.g. INV-20260816-0001)
        """
        today_str = timezone.now().strftime('%Y%m%d')
        prefix = f"INV-{today_str}-"
        last_sale = cls.objects.filter(invoice_number__startswith=prefix).order_by('-invoice_number').first()
        if last_sale:
            try:
                last_seq = int(last_sale.invoice_number.split('-')[-1])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1
        return f"{prefix}{new_seq:04d}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)

    @property
    def total_items_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_cost(self):
        """Total Cost of Goods Sold (COGS) for this transaction"""
        return sum(item.cost_price * item.quantity for item in self.items.all())

    @property
    def net_revenue(self):
        """Net product revenue (Subtotal minus discount)"""
        return max(Decimal('0.00'), self.subtotal - self.discount_amount)

    @property
    def net_profit(self):
        """Net profit generated from this sale in PKR"""
        if self.status == self.Status.REFUNDED or self.status == self.Status.CANCELLED:
            return Decimal('0.00')
        return self.net_revenue - self.total_cost

    @property
    def profit_margin_percent(self):
        """Profit margin percentage for this transaction"""
        if self.net_revenue > 0 and self.net_profit > 0:
            return round((self.net_profit / self.net_revenue) * 100, 1)
        return 0.0


class SaleItem(models.Model):
    """
    Line item for individual products & sizes sold in a transaction
    """
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items', verbose_name="Invoice")
    product = models.ForeignKey(
        'products.Product', 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='sale_items', 
        verbose_name="Product"
    )
    variant = models.ForeignKey(
        'products.ProductVariant', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sale_items', 
        verbose_name="Size / Variant"
    )
    
    # Snapshot fields in case product name or variant price changes in future
    product_name = models.CharField(max_length=200, verbose_name="Product Name Snapshot")
    variant_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Size Name Snapshot")
    
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Unit Selling Price (PKR)")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Cost Price (PKR)")
    quantity = models.IntegerField(default=1, verbose_name="Quantity")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Line Discount")
    total_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Line Total (PKR)")
    
    # Item-Level Refund Tracking
    is_refunded = models.BooleanField(default=False)
    refunded_quantity = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Sale Line Item"
        verbose_name_plural = "Sale Line Items"

    def __str__(self):
        desc = f"{self.product_name}"
        if self.variant_name:
            desc += f" ({self.variant_name})"
        return f"{desc} x {self.quantity} = PKR {self.total_price}"


class CashDrawerShift(models.Model):
    """
    Shift Management & Cash Drawer Reconciliation for operators
    """
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='shifts', 
        verbose_name="Cashier"
    )
    opening_time = models.DateTimeField(auto_now_add=True)
    closing_time = models.DateTimeField(blank=True, null=True)
    
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Opening Float (PKR)")
    closing_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Counted Closing Cash (PKR)")
    
    total_cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_wallet_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_refunds = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True, null=True, verbose_name="Shift Notes / Discrepancy Reason")

    class Meta:
        verbose_name = "Cash Drawer Shift"
        verbose_name_plural = "Cash Drawer Shifts"
        ordering = ['-opening_time']

    def __str__(self):
        return f"Shift #{self.pk} - {self.cashier.username} ({self.get_status_display()})"
