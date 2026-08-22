import threading
import requests
from django.db.models.signals import post_delete
from django.dispatch import receiver
from pakpos_project.apps.core.sync_worker import WEBHOOK_URLS
from pakpos_project.apps.core.logger import log_system_error

# Model to Table Mapping for Google Sheets
MODEL_TABLE_MAP = {
    'Sale': 'Sales',
    'SaleItem': 'SaleItems',
    'Customer': 'Customers',
    'Expense': 'Expenses',
    'ExpenseCategory': 'ExpenseCategories',
    'Product': 'Products',
    'ProductVariant': 'ProductVariants',
    'Category': 'Categories',
    'CashDrawerShift': 'Shifts',
    'DiningTable': 'Tables',
    'User': 'Users'
}

def _async_send_delete_webhook(table_name, record_id):
    """Background worker to notify Google Sheets to delete the corresponding row."""
    payload = {
        'action': 'delete_record',
        'table': table_name,
        'id': record_id
    }
    for webhook in WEBHOOK_URLS:
        try:
            requests.post(
                webhook,
                json=payload,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=15
            )
        except Exception as e:
            log_system_error("DeleteSyncSignal", f"Failed to sync delete for {table_name} id={record_id}: {e}")

def handle_post_delete_sync(sender, instance, **kwargs):
    """Generic post_delete handler triggered when any synced model is deleted from POS."""
    model_name = sender.__name__
    table_name = MODEL_TABLE_MAP.get(model_name)
    
    if table_name and hasattr(instance, 'id') and instance.id is not None:
        # Run deletion sync in background thread so POS UI remains blazing fast
        threading.Thread(
            target=_async_send_delete_webhook,
            args=(table_name, str(instance.id)),
            daemon=True
        ).start()

def register_delete_signals():
    """Register post_delete signals for all synced models."""
    from pakpos_project.apps.sales.models import Sale, Customer, SaleItem, CashDrawerShift, DiningTable
    from pakpos_project.apps.products.models import Product, ProductVariant, Category
    from pakpos_project.apps.expenses.models import Expense, ExpenseCategory
    from pakpos_project.apps.users.models import User

    synced_models = [
        Sale, Customer, SaleItem, CashDrawerShift, DiningTable,
        Product, ProductVariant, Category,
        Expense, ExpenseCategory, User
    ]

    for model in synced_models:
        post_delete.connect(handle_post_delete_sync, sender=model, weak=False)
