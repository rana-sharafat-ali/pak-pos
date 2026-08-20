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
