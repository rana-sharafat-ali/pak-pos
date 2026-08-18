from django.contrib import admin
from .models import Customer, Sale, SaleItem, CashDrawerShift, DiningTable


@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    list_display = ('name', 'floor_section', 'capacity', 'status', 'is_active', 'updated_at')
    list_filter = ('floor_section', 'status', 'is_active')
    search_fields = ('name', 'floor_section', 'notes')
    ordering = ('floor_section', 'name')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'created_at')
    search_fields = ('name', 'phone', 'email')


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('product_name', 'variant_name', 'unit_price', 'quantity', 'total_price')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'cashier', 'order_type', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'order_type', 'payment_method', 'created_at')
    search_fields = ('invoice_number', 'customer__name', 'customer__phone')
    inlines = [SaleItemInline]


@admin.register(CashDrawerShift)
class CashDrawerShiftAdmin(admin.ModelAdmin):
    list_display = ('cashier', 'status', 'opening_time', 'closing_time', 'opening_cash', 'closing_cash', 'total_cash_sales')
    list_filter = ('status', 'opening_time')
