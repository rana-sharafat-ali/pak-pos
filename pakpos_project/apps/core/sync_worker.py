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
                    email_job.error_message = str(e) + "\n" + traceback.format_exc()
                    email_job.save()
                    # We do NOT mark as 'failed' permanently unless we want to stop retrying.
                    # Currently keeping it 'pending' so it retries, but we might want to increment a retry counter.
                    # To keep it simple and strictly retry forever (offline-first):
                    pass
            
            # 2. PROCESS GOOGLE SHEETS SYNC (Batch of 5)
            # This is a placeholder for actual Google Sheets API integration
            # from pakpos_project.apps.expenses.models import Expense
            # expenses_to_sync = Expense.objects.filter(is_synced=False)[:5]
            # for exp in expenses_to_sync:
            #     # Sync logic here
            #     print(f"Syncing expense {exp.id} to Google Sheets...")
            #     exp.is_synced = True
            #     exp.save()
            
        except Exception as e:
            print(f"Sync worker encountered a critical error: {e}")
            
        # Sleep for 60 seconds (1 minute gap) as requested by user
        time.sleep(60)
