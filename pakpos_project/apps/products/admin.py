from django.contrib import admin
from .models import Product, ProductVariant, Category


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['name', 'cost_price', 'selling_price', 'stock_quantity', 'is_active']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'has_variants', 'price_display', 'stock_quantity', 'is_active']
    list_filter = ['category', 'has_variants', 'is_active']
    search_fields = ['name']
    inlines = [ProductVariantInline]
