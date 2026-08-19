import time
import threading
import traceback
from django.core.mail import EmailMultiAlternatives

# We avoid evaluating models at the top level to prevent AppRegistryNotReady errors
def start_sync_worker():
    thread = threading.Thread(target=sync_worker_loop, daemon=True)
    thread.start()

def sync_worker_loop():
    # Delay initial start to let Django finish booting
    time.sleep(10)
    
    from pakpos_project.apps.core.models import EmailQueue
    
    while True:
        try:
            # 1. PROCESS ONLY 1 EMAIL AT A TIME (FIFO)
            # Fetch the oldest pending email
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
                            
                        # Attempt to send (will raise exception if network fails)
                        msg.send(fail_silently=False)
                        
                        email_job.status = 'sent'
                        email_job.save()
                    else:
                        email_job.status = 'failed'
                        email_job.error_message = 'No valid recipient emails.'
                        email_job.save()
                except Exception as e:
                    # Network failure or SMTP error
                    error_str = str(e) + "\n" + traceback.format_exc()
                    email_job.error_message = error_str
                    email_job.save()
                    
                    # LOG THIS TO OUR SYSTEM LOGS SO IT SYNCS TO GOOGLE SHEETS
                    from pakpos_project.apps.core.logger import log_system_error
                    log_system_error("EmailWorker", f"Failed to send email to {email_job.get_emails()}: {str(e)}")
                    
                    # We do NOT mark as 'failed' permanently unless we want to stop retrying.
                    # Currently keeping it 'pending' so it retries, but we might want to increment a retry counter.
                    # To keep it simple and strictly retry forever (offline-first):
                    pass
            
            # 2. FETCH REMOTE ACTIONS FROM GOOGLE SHEETS
            WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwpoFtPWqsVLwB1jiKglEC5uHo8Ulk32uF6LgK47HfTA38TU9U1bGKayVjKAoolavQpLw/exec"  
            
            if WEBHOOK_URL:
                import json
                import requests
                
                # Import all models
                from pakpos_project.apps.sales.models import Sale, Customer, SaleItem, CashDrawerShift, DiningTable
                from pakpos_project.apps.products.models import Product, ProductVariant, Category
                from pakpos_project.apps.expenses.models import Expense, ExpenseCategory
                from pakpos_project.apps.users.models import User
                from pakpos_project.apps.core.logger import log_system_error, get_pending_logs, mark_logs_synced_and_prune
                
                models_to_sync = [
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
                
                try:
                    action_payload = {'table': 'Actions', 'fetch': True}
                    action_resp = requests.post(WEBHOOK_URL, json=action_payload, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    if action_resp.status_code == 200:
                        actions_json = action_resp.json()
                        if actions_json.get("success"):
                            actions_dict = actions_json.get("actions", {})
                            
                            # Execute "is_synced" action (Full Resync)
                            if actions_dict.get("is_synced") == "FALSE":
                                for model_class, tab_name in models_to_sync:
                                    model_class.objects.update(is_synced=False)
                                log_system_error("SyncWorker", "Remote Action executed: Full Database Resync triggered.")
                                
                            # Execute "clear_old_logs" action
                            if actions_dict.get("clear_old_logs") == "TRUE":
                                from pakpos_project.apps.core.logger import clear_all_logs
                                clear_all_logs()
                                # We don't log this because we literally just cleared the file!
                                
                except Exception as e:
                    log_system_error("SyncWorker", f"Failed to fetch remote actions: {e}")
                    
                # 3. PROCESS GOOGLE SHEETS SYNC
                
                for model_class, tab_name in models_to_sync:
                    records = list(model_class.objects.filter(is_synced=False)[:10])
                    if not records:
                        continue
                        
                    # Serialize records to simple dicts
                    payload_data = []
                    for record in records:
                        # Extract all fields dynamically
                        record_dict = {}
                        for field in record._meta.fields:
                            val = getattr(record, field.name)
                            # Convert dates and decimals to strings for JSON
                            if hasattr(val, 'isoformat'):
                                val = val.isoformat()
                            elif val is not None and not isinstance(val, (int, float, bool, str)):
                                val = str(val)
                            record_dict[field.name] = val
                        payload_data.append(record_dict)
                        
                    # Prepare POST request
                    payload = {
                        'table': tab_name,
                        'data': payload_data
                    }
                    
                    try:
                        response = requests.post(
                            WEBHOOK_URL, 
                            json=payload,
                            headers={'User-Agent': 'Mozilla/5.0'},
                            timeout=15,
                            allow_redirects=True
                        )
                        if response.status_code == 200:
                            # Mark as synced
                            for record in records:
                                record.is_synced = True
                                record.save(update_fields=['is_synced'])
                        else:
                            error_msg = f"Error syncing {tab_name} to Google Sheets: HTTP {response.status_code} - {response.text[:100]}"
                            log_system_error("SyncWorker", error_msg)
                    except Exception as e:
                        log_system_error("SyncWorker", f"Network Error syncing {tab_name} to Google Sheets: {e}")

                # 3. PROCESS TWO-WAY SYNC FOR LOGS
                pending_logs = get_pending_logs(10)
                # Even if there are no pending logs, we MUST sync to check for deletions from the Google Sheet
                # To trigger the Google Apps script to return existing_ids, we send an empty data array if no pending logs
                payload = {
                    'table': 'SystemLogs',
                    'data': pending_logs
                }
                try:
                    response = requests.post(
                        WEBHOOK_URL, 
                        json=payload,
                        headers={'User-Agent': 'Mozilla/5.0'},
                        timeout=15,
                        allow_redirects=True
                    )
                    if response.status_code == 200:
                        try:
                            res_json = response.json()
                            if res_json.get("success"):
                                existing_ids = res_json.get("existing_ids", [])
                                sent_log_ids = [l['id'] for l in pending_logs]
                                mark_logs_synced_and_prune(sent_log_ids, existing_ids)
                            else:
                                print(f"Google Sheets Log Sync returned error: {res_json.get('error')}")
                        except json.JSONDecodeError:
                            print(f"Invalid JSON response during log sync")
                    else:
                        print(f"HTTP Error during log sync: {response.status_code}")
                except Exception as e:
                    print(f"Network Error during log sync: {e}")
                    
        except Exception as e:
            # Absolute fallback if everything crashes
            print(f"Sync worker encountered a critical error: {e}")
            from pakpos_project.apps.core.logger import log_system_error
            log_system_error("SyncWorkerLoop", f"Critical Error: {e}\n{traceback.format_exc()}")
            
        # Sleep for 60 seconds (1 minute gap) as requested by user
        time.sleep(60)
