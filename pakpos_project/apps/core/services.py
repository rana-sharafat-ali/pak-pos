from pakpos_project.apps.core.models import SystemSetting


def get_current_system_settings():
    """
    Reads the current settings from the Singleton SystemSetting database.
    """
    settings = SystemSetting.load()
    return {
        'app_name': settings.app_name,
        'app_subtitle': settings.app_subtitle,
        'app_currency': settings.app_currency,
        'app_footer_text': settings.app_footer_text,
        'app_primary_color': settings.app_primary_color,
        'time_zone': settings.time_zone,
        'pos_operation_mode': settings.pos_operation_mode,
        'pos_default_tax_percent': float(settings.pos_default_tax_percent),
        'pos_default_service_charge_percent': float(settings.pos_default_service_charge_percent),
        'pos_default_discount_percent': float(settings.pos_default_discount_percent),
        'pos_auto_apply_discount': settings.pos_auto_apply_discount,
        'pos_default_delivery_charges': float(settings.pos_default_delivery_charges),
        'pos_shift_start_hour': settings.pos_shift_start_hour,
        'pos_shift_end_hour': settings.pos_shift_end_hour,
        'products_per_page': settings.products_per_page,
        'session_cookie_age_days': settings.session_cookie_age_days,
        'owner_email_1': settings.owner_email_1,
        'owner_email_2': settings.owner_email_2,
        'owner_email_3': settings.owner_email_3,
    }


def save_system_settings(cleaned_data):
    """
    Safely saves updated settings into the Singleton SystemSetting Database.
    Marks them as is_synced=False so the sync_worker can push them to Google Sheets.
    """
    settings = SystemSetting.load()
    changed = False

    for field in [
        'app_name', 'app_subtitle', 'app_currency', 'app_footer_text', 'app_primary_color',
        'time_zone', 'pos_operation_mode', 'pos_default_tax_percent', 'pos_default_service_charge_percent',
        'pos_default_discount_percent', 'pos_auto_apply_discount', 'pos_default_delivery_charges',
        'pos_shift_start_hour', 'pos_shift_end_hour', 'products_per_page', 'session_cookie_age_days',
        'owner_email_1', 'owner_email_2', 'owner_email_3'
    ]:
        if field in cleaned_data and cleaned_data[field] is not None:
            if getattr(settings, field) != cleaned_data[field]:
                setattr(settings, field, cleaned_data[field])
                changed = True

    if changed:
        settings.is_synced = False
        settings.save()


def queue_payment_reminder_email():
    """
    Renders and queues the payment due / subscription reminder email to all configured owner emails.
    """
    from pakpos_project.apps.core.models import EmailQueue, SystemSetting, PaymentAlert
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from pakpos_project.apps.core.logger import log_system_error
    
    try:
        settings = SystemSetting.load()
        alert_obj = PaymentAlert.load()
        
        emails = [e for e in [settings.owner_email_1, settings.owner_email_2, settings.owner_email_3] if e and '@' in e]
        if not emails:
            log_system_error("PaymentEmail", "Cannot send payment email: No owner emails configured in Settings.")
            return False
            
        context = {
            'app_name': settings.app_name or 'PakPOS',
            'app_subtitle': settings.app_subtitle or 'Professional POS System',
            'currency': settings.app_currency or 'PKR',
            'alert_title': alert_obj.alert_title or 'Software Subscription Payment Due',
            'alert_message': alert_obj.alert_message or 'Your monthly POS maintenance fee is pending. Please transfer the dues to keep services active.',
            'pending_month': alert_obj.pending_month or 'Current Month',
            'pending_amount': alert_obj.pending_amount or 'Rs. 0',
            'account_info': alert_obj.account_info or 'Please contact support for payment details.',
            'due_date': alert_obj.due_date,
            'contact_info': alert_obj.contact_info,
        }
        
        subject = f"⚠️ [Payment Notice] {context['alert_title']} - {context['pending_month']}"
        html_content = render_to_string('emails/payment_reminder_email.html', context)
        text_content = strip_tags(html_content)
        
        email_job = EmailQueue(
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            status='pending'
        )
        email_job.set_emails(emails)
        email_job.save()
        log_system_error("PaymentEmail", f"Payment reminder email queued for: {', '.join(emails)}")
        return True
    except Exception as e:
        log_system_error("PaymentEmail", f"Failed to queue payment reminder email: {e}")
        return False

