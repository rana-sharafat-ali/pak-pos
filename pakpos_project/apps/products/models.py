from django.db import models
from django.urls import reverse
from decimal import Decimal


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Category Name")
    icon = models.CharField(max_length=20, default='📦', blank=True, verbose_name="Category Emoji / Icon")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return f"{self.icon} {self.name}" if self.icon else self.name


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="Product Name")
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='products', 
        verbose_name="Category"
    )
    has_variants = models.BooleanField(
        default=False, 
        verbose_name="Has Sizes / Variations (e.g. Small, Medium, Large)"
    )
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        blank=True,
        verbose_name="Selling Price (PKR)"
    )
    cost_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        blank=True,
        verbose_name="Cost Price (PKR)"
    )
    stock_quantity = models.IntegerField(default=0, blank=True, verbose_name="Stock Quantity")
    track_stock = models.BooleanField(default=True, verbose_name="Track Stock Quantity")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Active for Sale")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:product_detail', kwargs={'pk': self.pk})

    @property
    def variant_count(self):
        if self.has_variants:
            active_count = self.variants.filter(is_active=True).count()
            return active_count if active_count > 0 else self.variants.count()
        return 0

    @property
    def price_display(self):
        """
        Returns formatted price display e.g. PKR 500 or PKR 500 - PKR 1,400
        """
        if self.has_variants:
            variants = list(self.variants.filter(is_active=True))
            if not variants:
                variants = list(self.variants.all())
            if variants:
                prices = [v.selling_price for v in variants if v.selling_price is not None]
                if prices:
                    min_p, max_p = min(prices), max(prices)
                    if min_p == max_p:
                        return f"PKR {min_p}"
                    return f"PKR {min_p} - {max_p}"
            return "No sizes configured"
        return f"PKR {self.base_price}"

    @property
    def profit_margin(self):
        if not self.has_variants and self.base_price > 0 and self.cost_price > 0:
            profit = self.base_price - self.cost_price
            return round((profit / self.base_price) * 100, 1)
        return 0.0

    @property
    def total_stock(self):
        if self.has_variants:
            return sum(v.stock_quantity for v in self.variants.all())
        return self.stock_quantity


class ProductVariant(models.Model):
    """
    Represents a specific Size or Variation of a product (e.g. Small, Medium, Large, Family)
    """
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='variants', 
        verbose_name="Product"
    )
    name = models.CharField(max_length=100, verbose_name="Size / Variation Name (e.g. Small, Medium, Large)")
    cost_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        blank=True,
        verbose_name="Cost Price (PKR)"
    )
    selling_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        verbose_name="Selling Price (PKR)"
    )
    stock_quantity = models.IntegerField(default=0, blank=True, verbose_name="Stock Quantity")
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Product Size / Variant"
        verbose_name_plural = "Product Sizes / Variants"
        ordering = ['selling_price']

    def __str__(self):
        return f"{self.product.name} - {self.name} (PKR {self.selling_price})"

    @property
    def profit_margin(self):
        if self.selling_price > 0 and self.cost_price > 0:
            profit = self.selling_price - self.cost_price
            return round((profit / self.selling_price) * 100, 1)
        return 0.0
