import time
import threading
import traceback
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections

from django.conf import settings
import os

# =========================================================
# GLOBAL WEBHOOK CONFIGURATION
# =========================================================
# Try to get from settings (if configured), fallback to os.environ, otherwise use hardcoded.
webhook_from_env = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL')
WEBHOOK_URLS = [webhook_from_env] if webhook_from_env else [
    "https://script.google.com/macros/s/AKfycbxiTjw3CU_dFFOfEZ0xizJHt-_Cd1Y2vogkB-1E9DdD4tlsGhaqdDjBFj-NFDzu070N/exec"
]

# We avoid evaluating models at the top level to prevent AppRegistryNotReady errors
def start_sync_worker():
    threads = [
        threading.Thread(target=email_worker_loop, daemon=True),
        threading.Thread(target=action_worker_loop, daemon=True),
        threading.Thread(target=setting_worker_loop, daemon=True),
        threading.Thread(target=data_sync_worker_loop, daemon=True),
        threading.Thread(target=log_sync_worker_loop, daemon=True)
    ]
    for thread in threads:
        thread.start()

# ---------------------------------------------------------
# 1. EMAIL WORKER (1 Minute Interval, 20 Min Sleep on Pause)
# ---------------------------------------------------------
def email_worker_loop():
    time.sleep(10) # Initial boot delay
    from pakpos_project.apps.core.models import EmailQueue, SystemSetting
    from pakpos_project.apps.core.logger import log_system_error
    
    while True:
        close_old_connections()
        synced_anything = False
        try:
            # Check if email sending is enabled via remote action
            settings = SystemSetting.load()
            if not getattr(settings, 'email_enabled', True):
                # Email sending is disabled via remote action: Sleep for 20 minutes (1200 seconds) without performing heavy tasks
                close_old_connections()
                time.sleep(1200) # 20 Minute sleep
                continue

            email_job = EmailQueue.objects.filter(status='pending').order_by('created_at').first()
            if email_job:
                try:
                    emails = email_job.get_emails()
                    if emails:
                        msg = EmailMultiAlternatives(
                            subject=email_job.subject,
                            body=email_job.text_content,
                            to=emails
                        )
                        if email_job.html_content:
                            msg.attach_alternative(email_job.html_content, "text/html")
                            
                        msg.send(fail_silently=False)
                        email_job.status = 'sent'
                        email_job.save()
                        synced_anything = True
                    else:
                        email_job.status = 'failed'
                        email_job.error_message = 'No valid recipient emails.'
                        email_job.save()
                except Exception as e:
                    error_str = str(e) + "\n" + traceback.format_exc()
                    email_job.error_message = error_str
                    email_job.save()
                    log_system_error("EmailWorker", f"Failed to send email to {email_job.get_emails()}: {str(e)}")
            
            if synced_anything:
                log_system_error("EmailWorker", "100% Complete")
                
        except Exception as e:
            log_system_error("EmailWorker", f"Critical Error: {e}")
            
        time.sleep(100) # Normal Interval

# ---------------------------------------------------------
# 2. ACTION WORKER (5 Minute Interval)
# ---------------------------------------------------------
def action_worker_loop():
    time.sleep(15)
    import json
    import requests
    from pakpos_project.apps.core.logger import log_system_error
    from pakpos_project.apps.core.utils import get_setting
    
    while True:
        close_old_connections()
        synced_anything = False
        try:
            action_payload = {'table': 'Actions', 'fetch': True}
            for webhook in WEBHOOK_URLS:
                try:
                    action_resp = requests.post(webhook, json=action_payload, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    if action_resp.status_code == 200:
                        try:
                            actions_json = action_resp.json()
                            if actions_json.get("success"):
                                actions_dict = actions_json.get("actions", {})
                                
                                # Execute "is_synced" action (Full Resync)
                                if str(actions_dict.get("is_synced")).strip().upper() == "FALSE":
                                    from pakpos_project.apps.sales.models import Sale, Customer, SaleItem, CashDrawerShift, DiningTable
                                    from pakpos_project.apps.products.models import Product, ProductVariant, Category
                                    from pakpos_project.apps.expenses.models import Expense, ExpenseCategory
                                    from pakpos_project.apps.users.models import User
                                    from pakpos_project.apps.core.models import SystemSetting
                                    models_to_reset = [SystemSetting, Sale, SaleItem, Customer, Expense, ExpenseCategory, Product, ProductVariant, Category, CashDrawerShift, DiningTable, User]
                                    for model_class in models_to_reset:
                                        model_class.objects.update(is_synced=False)
                                    log_system_error("ActionWorker", "Remote Action executed: Full Database Resync triggered.")
                                    synced_anything = True

                                # Execute "email_active" action (Enable / Disable Email Sending)
                                for k, v in actions_dict.items():
                                    k_norm = str(k).strip().lower()
                                    if k_norm in ["email_active", "email_enabled", "send_email", "email", "email_sending"]:
                                        is_email_active = str(v).strip().upper() in ["TRUE", "1", "YES", "T", "ON", "ENABLE", "ENABLED"]
                                        from pakpos_project.apps.core.models import SystemSetting
                                        settings = SystemSetting.load()
                                        if getattr(settings, 'email_enabled', True) != is_email_active:
                                            settings.email_enabled = is_email_active
                                            settings.save(update_fields=['email_enabled'])
                                            log_system_error("ActionWorker", f"Email sending toggled to: {is_email_active}")
                                        break

                                # Execute "payment_email" trigger (One-time payment reminder email)
                                for k, v in actions_dict.items():
                                    k_norm = str(k).strip().lower()
                                    if k_norm in ["payment_email", "send_payment_email", "payment_email_active", "payment_email_trigger"]:
                                        if str(v).strip().upper() in ["TRUE", "1", "YES", "T", "ON", "ENABLE", "ENABLED"]:
                                            from pakpos_project.apps.core.services import queue_payment_reminder_email
                                            queue_payment_reminder_email()
                                        break

                                    
                        except json.JSONDecodeError as e:
                            log_system_error("ActionWorker", f"Failed to parse remote actions from {webhook}: {e}")
                except Exception as e:
                    log_system_error("ActionWorker", f"Network error fetching remote actions: {e}")
            
            if synced_anything:
                log_system_error("ActionWorker", "100% Complete")
                
        except Exception as e:
            log_system_error("ActionWorker", f"Critical Error: {e}")
        finally:
            close_old_connections()
            
        time.sleep(300) # 5 Minute Interval


# ---------------------------------------------------------
# 3. SETTING WORKER (5 Minute Interval)
# ---------------------------------------------------------
def setting_worker_loop():
    time.sleep(20)
    import json
    import requests
    from pakpos_project.apps.core.logger import log_system_error
    from pakpos_project.apps.core.models import SystemSetting
    
    while True:
        close_old_connections()
        synced_anything = False
        try:
            settings_payload = {'table': 'SystemSettings', 'fetch': True}
            for webhook in WEBHOOK_URLS:
                try:
                    settings_resp = requests.post(webhook, json=settings_payload, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    if settings_resp.status_code == 200:
                        try:
                            settings_json = settings_resp.json()
                            if settings_json.get("success"):

                                remote_settings = settings_json.get("actions", {}) 
                                
                                if remote_settings:
                                    settings = SystemSetting.load()
                                    changed = False
                                    
                                    for key, val in remote_settings.items():
                                        key = str(key).strip()
                                        if not hasattr(settings, key) or key in ['id', 'is_synced', 'updated_at']:
                                            continue
                                            
                                        val = str(val).strip()
                                        
                                        # Type Conversion
                                        if key == 'pos_operation_mode':
                                            val = val.lower()
                                            if val not in ['retail', 'restaurant', 'cafe', 'fast_food']:
                                                val = 'restaurant' 
                                        elif key == 'pos_auto_apply_discount':
                                            val = True if val.upper() in ["TRUE", "1", "YES", "T"] else False
                                        elif key in ['pos_shift_start_hour', 'pos_shift_end_hour', 'products_per_page', 'session_cookie_age_days']:
                                            try: val = int(float(val))
                                            except ValueError: continue 
                                        elif 'percent' in key or 'charges' in key:
                                            try: val = float(val)
                                            except ValueError: continue 
                                                
                                        # Update if changed remotely
                                        # We only update if local is_synced=True, meaning no pending local changes.
                                        if settings.is_synced and getattr(settings, key) != val:
                                            setattr(settings, key, val)
                                            changed = True
                                            
                                    if changed:
                                        settings.is_synced = True # Mark as synced since we just pulled from remote
                                        settings.save()
                                        synced_anything = True
                        except json.JSONDecodeError as e:
                            log_system_error("SettingWorker", f"Failed to parse remote settings: {e}")
                except Exception as e:
                    log_system_error("SettingWorker", f"Network error fetching remote settings: {e}")
            
            if synced_anything:
                log_system_error("SettingWorker", "100% Complete")
                
        except Exception as e:
            log_system_error("SettingWorker", f"Critical Error: {e}")
        finally:
            close_old_connections()
            
        time.sleep(300) # Slowed down to 60 seconds (1 minute)

# ---------------------------------------------------------
# 4. DATA SYNC WORKER (5 Minute Interval, 50 Items)
# ---------------------------------------------------------
def data_sync_worker_loop():
    time.sleep(25)
    import requests
    from pakpos_project.apps.core.logger import log_system_error
    from pakpos_project.apps.sales.models import Sale, Customer, SaleItem, CashDrawerShift, DiningTable
    from pakpos_project.apps.products.models import Product, ProductVariant, Category
    from pakpos_project.apps.expenses.models import Expense, ExpenseCategory
    from pakpos_project.apps.users.models import User
    from pakpos_project.apps.core.models import SystemSetting
    
    models_to_sync = [
        (SystemSetting, 'SystemSettings'),
        (Sale, 'Sales'),
        (SaleItem, 'SaleItems'),
        (Customer, 'Customers'),
        (Expense, 'Expenses'),
        (ExpenseCategory, 'ExpenseCategories'),
        (Product, 'Products'),
        (ProductVariant, 'ProductVariants'),
        (Category, 'Categories'),
        (CashDrawerShift, 'Shifts'),
        (DiningTable, 'Tables'),
        (User, 'Users'),
    ]
    
    while True:
        close_old_connections()
        synced_anything = False
        try:
            for model_class, tab_name in models_to_sync:
                try:
                    records = list(model_class.objects.filter(is_synced=False)[:50]) # Chunks of 50
                    if not records: continue
                        
                    payload_data = []
                    for record in records:
                        record_dict = {}
                        for field in record._meta.fields:
                            val = getattr(record, field.name)
                            if hasattr(val, 'isoformat'): val = val.isoformat()
                            elif val is not None and not isinstance(val, (int, float, bool, str)): val = str(val)
                            record_dict[field.name] = val
                        payload_data.append(record_dict)
                        
                    payload = {'table': tab_name, 'data': payload_data}
                    
                    all_webhooks_success = True
                    for webhook in WEBHOOK_URLS:
                        try:
                            response = requests.post(webhook, json=payload, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20, allow_redirects=True)
                            if response.status_code != 200:
                                all_webhooks_success = False
                                log_system_error("DataSyncWorker", f"Error syncing {tab_name}: HTTP {response.status_code}")
                        except Exception as e:
                            all_webhooks_success = False
                            log_system_error("DataSyncWorker", f"Network Error syncing {tab_name}: {e}")

                    if all_webhooks_success:
                        for record in records:
                            record.is_synced = True
                            record.save(update_fields=['is_synced'])
                        synced_anything = True
                except Exception as e:
                    log_system_error("DataSyncWorker", f"Failed to sync table {tab_name}: {e}")
                    continue
                    
            if synced_anything:
                log_system_error("DataSyncWorker", "100% Complete")
                
        except Exception as e:
            log_system_error("DataSyncWorker", f"Critical Error: {e}")
        finally:
            close_old_connections()
            
        time.sleep(300) # Slowed down to 30 seconds

# ---------------------------------------------------------
# 5. LOG SYNC WORKER (10 Minute Interval, 200 Items)
# ---------------------------------------------------------
def log_sync_worker_loop():
    time.sleep(30)
    import requests
    import json
    from pakpos_project.apps.core.logger import get_pending_logs, mark_logs_synced_and_prune, log_system_error
    
    while True:
        close_old_connections()
        try:
            pending_logs = get_pending_logs(200) # Chunks of 200
            if pending_logs:
                payload = {'table': 'SystemLogs', 'data': pending_logs}
                all_existing_ids = []
                success = True
                
                for idx, webhook in enumerate(WEBHOOK_URLS):
                    try:
                        response = requests.post(webhook, json=payload, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20, allow_redirects=True)
                        if response.status_code == 200:
                            try:
                                res_json = response.json()
                                if res_json.get("success"):
                                    existing_ids = res_json.get("existing_ids", [])
                                    if idx == 0:
                                        all_existing_ids = existing_ids
                                    else:
                                        all_existing_ids = [eid for eid in all_existing_ids if eid in existing_ids]
                                else:
                                    success = False
                            except json.JSONDecodeError:
                                success = False
                        else:
                            success = False
                    except Exception as e:
                        success = False
                        
                if success:
                    sent_log_ids = [l['id'] for l in pending_logs]
                    mark_logs_synced_and_prune(sent_log_ids, all_existing_ids)
                    
        except Exception as e:
            log_system_error("LogSyncWorker", f"Critical Error: {e}")
        finally:
            close_old_connections()
            
        time.sleep(600) # 10 Minute Interval 600
