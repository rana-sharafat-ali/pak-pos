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
    
    # JSON APIs
    path('api/checkout/', views.api_create_sale, name='api_checkout'),
    path('api/customers/search/', views.api_search_customers, name='api_customer_search'),
]
