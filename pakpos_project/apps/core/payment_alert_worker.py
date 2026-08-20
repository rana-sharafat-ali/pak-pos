import os
import time
import json
import threading
import requests
import re
from datetime import datetime
from django.db import close_old_connections
from pakpos_project.apps.core.logger import log_system_error

# =========================================================
# GLOBAL WEBHOOK CONFIGURATION
# =========================================================
webhook_from_env = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL')
WEBHOOK_URLS = [webhook_from_env] if webhook_from_env else [
    "https://script.google.com/macros/s/AKfycbxiTjw3CU_dFFOfEZ0xizJHt-_Cd1Y2vogkB-1E9DdD4tlsGhaqdDjBFj-NFDzu070N/exec"
]

def format_clean_month_string(raw_val):
    if not raw_val:
        return ""
    val_str = str(raw_val).strip()
    for tz in ["GMT", "PKT", "UTC", "+0500", "+0000"]:
        val_str = val_str.replace(tz, "")
    val_str = re.sub(r'\(.*?\)', '', val_str).strip()
    
    formats_to_try = [
        "%a %b %d %Y %H:%M:%S",
        "%a %b %d %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%b %Y",
        "%B %Y",
        "%m/%Y",
    ]
    for fmt in formats_to_try:
        try:
            candidate = re.sub(r'\s+', ' ', val_str).strip()
            dt = datetime.strptime(candidate, fmt)
            return dt.strftime("%B %Y")
        except Exception:
            continue
            
    clean_fallback = re.sub(r'\b\d{2}:\d{2}:\d{2}\b', '', val_str)
    clean_fallback = re.sub(r'[+\-]\d{4}', '', clean_fallback)
    clean_fallback = re.sub(r'\s+', ' ', clean_fallback).strip()
    return clean_fallback or raw_val

def format_clean_date_string(raw_val):
    if not raw_val:
        return ""
    val_str = str(raw_val).strip()
    for tz in ["GMT", "PKT", "UTC", "+0500", "+0000"]:
        val_str = val_str.replace(tz, "")
    val_str = re.sub(r'\(.*?\)', '', val_str).strip()
    
    formats_to_try = [
        "%a %b %d %Y %H:%M:%S",
        "%a %b %d %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]
    for fmt in formats_to_try:
        try:
            candidate = re.sub(r'\s+', ' ', val_str).strip()
            dt = datetime.strptime(candidate, fmt)
            return dt.strftime("%d-%B-%Y")
        except Exception:
            continue
            
    clean_fallback = re.sub(r'\b\d{2}:\d{2}:\d{2}\b', '', val_str)
    clean_fallback = re.sub(r'[+\-]\d{4}', '', clean_fallback)
    clean_fallback = re.sub(r'\s+', ' ', clean_fallback).strip()
    return clean_fallback or raw_val


def payment_alert_worker_loop():
    """
    Background worker loop to continuously synchronize Payment Due Alerts
    from Google Sheets 'Actions' tab into the local database singleton.
    Offline-safe: Never crashes on internet disconnects.
    """
    time.sleep(10) # Initial startup delay
    from pakpos_project.apps.core.models import PaymentAlert

    while True:
        close_old_connections()
        try:
            payload = {'table': 'Actions', 'fetch': True}
            
            for webhook in WEBHOOK_URLS:
                if not webhook:
                    continue
                try:
                    resp = requests.post(webhook, json=payload, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("success"):
                            actions = data.get("actions", {})
                            
                            # Normalize all keys to lowercase for flexible matching
                            normalized_actions = {str(k).strip().lower(): str(v).strip() for k, v in actions.items() if k is not None}
                            
                            alert_obj = PaymentAlert.load()
                            changed = False

                            # 1. Popup Active Status Check
                            popup_val = (
                                normalized_actions.get("popup_alert_active") or
                                normalized_actions.get("payment_popup_active") or
                                normalized_actions.get("popup_active") or
                                normalized_actions.get("payment_alert_active")
                            )
                            if popup_val is not None:
                                is_popup = popup_val.upper() in ["TRUE", "1", "YES", "T", "ON", "ENABLE", "ENABLED"]
                                if alert_obj.is_popup_active != is_popup:
                                    alert_obj.is_popup_active = is_popup
                                    changed = True

                            # 2. Navbar Badge Active Status Check
                            navbar_val = (
                                normalized_actions.get("navbar_alert_active") or
                                normalized_actions.get("payment_navbar_active") or
                                normalized_actions.get("navbar_active")
                            )
                            if navbar_val is not None:
                                is_navbar = navbar_val.upper() in ["TRUE", "1", "YES", "T", "ON", "ENABLE", "ENABLED"]
                                if alert_obj.is_navbar_active != is_navbar:
                                    alert_obj.is_navbar_active = is_navbar
                                    changed = True
                            # 3. Email Sending Status Check
                            # 3. Email Sending Status Check (Global Pause/Resume)
                            email_val = (
                                normalized_actions.get("email_active") or
                                normalized_actions.get("email_enabled") or
                                normalized_actions.get("send_email") or
                                normalized_actions.get("email") or
                                normalized_actions.get("email_sending")
                            )
                            if email_val is not None:
                                is_email = email_val.upper() in ["TRUE", "1", "YES", "T", "ON", "ENABLE", "ENABLED"]
                                from pakpos_project.apps.core.models import SystemSetting
                                settings_obj = SystemSetting.load()
                                if getattr(settings_obj, 'email_enabled', True) != is_email:
                                    settings_obj.email_enabled = is_email
                                    settings_obj.save(update_fields=['email_enabled'])
                                    log_system_error("PaymentAlertWorker", f"Email sending toggled to: {is_email}")

                            # 4. One-Time Payment Notice Email Trigger (Auto-Reverts to FALSE)
                            send_email_action = (
                                normalized_actions.get("payment_email") or
                                normalized_actions.get("send_payment_email") or
                                normalized_actions.get("payment_email_active") or
                                normalized_actions.get("payment_email_trigger")
                            )
                            if send_email_action and send_email_action.upper() in ["TRUE", "1", "YES", "T", "ON", "ENABLE", "ENABLED"]:
                                from pakpos_project.apps.core.services import queue_payment_reminder_email
                                queue_payment_reminder_email()

                            # 5. Interval (in minutes)



                            interval_val = (
                                normalized_actions.get("payment_alert_interval") or 
                                normalized_actions.get("payment_alert_interval_minutes") or 
                                normalized_actions.get("alert_interval") or 
                                normalized_actions.get("alert_time")
                            )
                            if interval_val:
                                try:
                                    parsed_interval = max(1, int(float(interval_val)))
                                    if alert_obj.interval_minutes != parsed_interval:
                                        alert_obj.interval_minutes = parsed_interval
                                        changed = True
                                except ValueError:
                                    pass

                            # 3. Pending Month / Period
                            month_val = (
                                normalized_actions.get("payment_pending_month") or 
                                normalized_actions.get("payment_month") or 
                                normalized_actions.get("pending_month") or 
                                normalized_actions.get("due_month")
                            )
                            if month_val:
                                month_val = format_clean_month_string(month_val)
                                if alert_obj.pending_month != month_val:
                                    alert_obj.pending_month = month_val
                                    changed = True

                            # 4. Pending Amount
                            amount_val = (
                                normalized_actions.get("payment_pending_amount") or 
                                normalized_actions.get("payment_amount") or 
                                normalized_actions.get("pending_amount") or 
                                normalized_actions.get("due_amount")
                            )
                            if amount_val and alert_obj.pending_amount != amount_val:
                                alert_obj.pending_amount = amount_val
                                changed = True

                            # 5. Account / Bank Information
                            account_val = (
                                normalized_actions.get("payment_account_info") or 
                                normalized_actions.get("account_info") or 
                                normalized_actions.get("bank_details") or 
                                normalized_actions.get("bank_info") or 
                                normalized_actions.get("payment_details")
                            )
                            if account_val and alert_obj.account_info != account_val:
                                alert_obj.account_info = account_val
                                changed = True

                            # 6. Title
                            title_val = normalized_actions.get("payment_alert_title") or normalized_actions.get("alert_title")
                            if title_val and alert_obj.alert_title != title_val:
                                alert_obj.alert_title = title_val
                                changed = True

                            # 7. Custom Message / Instructions
                            msg_val = normalized_actions.get("payment_alert_message") or normalized_actions.get("alert_message") or normalized_actions.get("payment_message")
                            if msg_val and alert_obj.alert_message != msg_val:
                                alert_obj.alert_message = msg_val
                                changed = True

                            # 8. Due Date
                            due_date_val = normalized_actions.get("payment_due_date") or normalized_actions.get("due_date")
                            if due_date_val:
                                due_date_val = format_clean_date_string(due_date_val)
                                if alert_obj.due_date != due_date_val:
                                    alert_obj.due_date = due_date_val
                                    changed = True


                            # 9. Support Contact Info
                            contact_val = normalized_actions.get("payment_contact_info") or normalized_actions.get("contact_info") or normalized_actions.get("support_contact")
                            if contact_val and alert_obj.contact_info != contact_val:
                                alert_obj.contact_info = contact_val
                                changed = True

                            if changed:
                                alert_obj.save()
                                log_system_error("PaymentAlertWorker", f"Payment Alert config updated: Active={alert_obj.is_active}, Month={alert_obj.pending_month}, Interval={alert_obj.interval_minutes}m")

                except Exception as e:
                    # Offline safety: Ignore transient network failures
                    pass
        except Exception as e:
            log_system_error("PaymentAlertWorker", f"Critical loop error: {e}")
        finally:
            close_old_connections()

        # Polling frequency (Every 60 seconds)
        time.sleep(60)


def start_payment_alert_worker():
    """
    Launch the Payment Alert Worker daemon thread.
    """
    t = threading.Thread(target=payment_alert_worker_loop, daemon=True, name="PaymentAlertWorkerThread")
    t.start()
