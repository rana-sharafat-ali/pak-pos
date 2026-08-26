import time
import threading
import traceback
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections, models

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
        threading.Thread(target=log_sync_worker_loop, daemon=True),
        threading.Thread(target=gdrive_backup_worker_loop, daemon=True),
        threading.Thread(target=maintenance_worker_loop, daemon=True)
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
            
        time.sleep(60) # 1 Minute Interval

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

                                # Execute "backup_active" action (Enable / Disable Google Drive Backup)
                                for k, v in actions_dict.items():
                                    k_norm = str(k).strip().lower()
                                    if k_norm in ["backup_active", "gdrive_backup_active", "backup_enabled", "cloud_backup_active"]:
                                        is_backup_active = str(v).strip().upper() in ["TRUE", "1", "YES", "T", "ON", "ENABLE", "ENABLED"]
                                        from pakpos_project.apps.core.models import SystemSetting
                                        settings = SystemSetting.load()
                                        if getattr(settings, 'gdrive_remote_active', True) != is_backup_active:
                                            settings.gdrive_remote_active = is_backup_active
                                            settings.save(update_fields=['gdrive_remote_active'])
                                            log_system_error("ActionWorker", f"Remote backup permission toggled to: {is_backup_active}")
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
            
        time.sleep(60) # 1 Minute Interval


# ---------------------------------------------------------
# 2.5. GDRIVE BACKUP WORKER (Scheduled Daily Cloud Upload)
# ---------------------------------------------------------
def gdrive_backup_worker_loop():
    time.sleep(15)
    from pakpos_project.apps.core.models import SystemSetting
    from pakpos_project.apps.core.logger import log_system_error
    from django.utils import timezone
    from pakpos_project.apps.core.views import perform_gdrive_backup

    last_auto_triggered_slot = ""

    while True:
        close_old_connections()
        try:
            settings_obj = SystemSetting.load()
            if settings_obj.gdrive_backup_enabled and getattr(settings_obj, 'gdrive_remote_active', True):
                sched_time = (settings_obj.gdrive_backup_time or "23:00").strip()
                now = timezone.localtime()
                now_hm = now.strftime('%H:%M')
                today_slot = f"{now.strftime('%Y-%m-%d')}_{sched_time}"

                # Compare current time with scheduled time
                # Also normalize leading zeros (e.g. "09:00" vs "9:00")
                sched_parts = sched_time.split(':')
                if len(sched_parts) == 2:
                    try:
                        sched_norm = f"{int(sched_parts[0]):02d}:{int(sched_parts[1]):02d}"
                    except ValueError:
                        sched_norm = sched_time
                else:
                    sched_norm = sched_time

                if now_hm == sched_norm and last_auto_triggered_slot != today_slot:
                    last_auto_triggered_slot = today_slot
                    log_system_error("GDriveWorker", f"Scheduled daily backup triggered for {sched_norm}")
                    perform_gdrive_backup(settings_obj)

        except Exception as e:
            log_system_error("GDriveWorker", f"Error in backup worker: {e}")
        finally:
            close_old_connections()

        time.sleep(30) # 30 second loop ensures we never miss the minute window


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
                                    
                                    for key, raw_val in remote_settings.items():
                                        key = str(key).strip()
                                        if not hasattr(settings, key) or key in ['id', 'is_synced', 'updated_at']:
                                            continue
                                        
                                        try:
                                            field = settings._meta.get_field(key)
                                        except Exception:
                                            continue
                                            
                                        str_val = str(raw_val).strip() if raw_val is not None else ''
                                        
                                        # Accurate Django Field Type Conversions
                                        if isinstance(field, models.BooleanField):
                                            val = True if str_val.upper() in ["TRUE", "1", "YES", "T"] else False
                                        elif isinstance(field, (models.IntegerField, models.SmallIntegerField, models.PositiveIntegerField)):
                                            try: val = int(float(str_val))
                                            except (ValueError, TypeError): continue
                                        elif isinstance(field, (models.DecimalField, models.FloatField)):
                                            try: val = float(str_val)
                                            except (ValueError, TypeError): continue
                                        elif key == 'pos_operation_mode':
                                            val = str_val.lower()
                                            if val not in ['retail', 'restaurant', 'cafe', 'fast_food']:
                                                val = 'restaurant'
                                        else:
                                            val = str_val
                                                
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
            
        time.sleep(60) # 1 Minute Interval

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
                            if field.is_relation and field.many_to_one:
                                fk_val = getattr(record, field.attname)
                                record_dict[field.name] = str(fk_val) if fk_val is not None else ''
                                record_dict[field.attname] = str(fk_val) if fk_val is not None else ''
                            else:
                                val = getattr(record, field.name)
                                if hasattr(val, 'isoformat'): val = val.isoformat()
                                elif val is not None and not isinstance(val, (int, float, bool, str)): val = str(val)
                                record_dict[field.name] = val
                        
                        # Extra helper fields for relational clarity in Sheets
                        if tab_name == 'SaleItems' and hasattr(record, 'sale') and record.sale:
                            record_dict['invoice_number'] = record.sale.invoice_number
                            record_dict['sale_id'] = str(record.sale_id)
                            record_dict['sale'] = str(record.sale_id)

                        if tab_name == 'Sales':
                            if hasattr(record, 'customer') and record.customer:
                                record_dict['customer_name'] = record.customer.name
                                record_dict['customer_phone'] = record.customer.phone or ''
                                record_dict['customer_email'] = record.customer.email or ''
                            else:
                                record_dict['customer_name'] = 'Walk-in Customer'
                                record_dict['customer_phone'] = ''

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
            
        time.sleep(60) # 1 Minute Interval

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
            
        time.sleep(60) # 1 Minute Interval

# ---------------------------------------------------------
# 6. MAINTENANCE WORKER (Daily Google Sheets Cleanup)
# ---------------------------------------------------------
def maintenance_worker_loop():
    time.sleep(60) # Wait 60 seconds on boot
    import requests
    from pakpos_project.apps.core.logger import log_system_error
    from django.utils import timezone
    
    last_cleanup_day = None
    
    while True:
        close_old_connections()
        try:
            today = timezone.localtime().strftime('%Y-%m-%d')
            # Run cleanup once a day at midnight or first boot of the day
            if today != last_cleanup_day:
                payload = {'action': 'cleanup_old_data', 'days': 365}
                all_success = True
                
                for webhook in WEBHOOK_URLS:
                    try:
                        response = requests.post(webhook, json=payload, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
                        if response.status_code != 200:
                            all_success = False
                    except Exception as e:
                        all_success = False
                
                if all_success:
                    last_cleanup_day = today
                    log_system_error("MaintenanceWorker", "Triggered remote 365-day Google Sheets cleanup successfully.")
                    
        except Exception as e:
            log_system_error("MaintenanceWorker", f"Critical Error: {e}")
        finally:
            close_old_connections()
            
        time.sleep(3600) # Check every hour if day has changed
