from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    # POS Terminal
    path('', views.pos_terminal_view, name='pos'),
    
    # Invoices & History
    path('history/', views.sales_ledger_view, name='ledger'),
    path('receipt/<int:pk>/', views.receipt_view, name='receipt'),
    path('invoice/<int:pk>/', views.invoice_a4_view, name='invoice_a4'),
    path('refund/<int:pk>/', views.sale_refund_view, name='refund'),
    
    # Daily Shift & Cash Reconciliation
    path('shift/', views.daily_shift_summary_view, name='shift_summary'),
    path('shift/print/', views.shift_print_view, name='shift_print'),
    
    # Restaurant Dining Tables Management
    path('tables/', views.table_list_view, name='table_list'),
    path('tables/create/', views.table_create_view, name='table_create'),
    path('tables/<int:pk>/edit/', views.table_update_view, name='table_update'),
    path('tables/<int:pk>/delete/', views.table_delete_view, name='table_delete'),
    path('tables/bulk-delete/', views.table_bulk_delete_view, name='table_bulk_delete'),

    # Customer Management & Directory (CRM)
    path('customers/', views.customer_list_view, name='customer_list'),
    path('customers/create/', views.customer_create_view, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail_view, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_update_view, name='customer_update'),
    path('customers/<int:pk>/delete/', views.customer_delete_view, name='customer_delete'),
    path('customers/bulk-delete/', views.customer_bulk_delete_view, name='customer_bulk_delete'),

    # JSON APIs
    path('api/checkout/', views.api_create_sale, name='api_checkout'),
    path('api/customers/search/', views.api_search_customers, name='api_customer_search'),
    path('api/customers/create/', views.api_create_customer, name='api_customer_create'),
    path('api/products/search/', views.api_search_products, name='api_search_products'),
]
