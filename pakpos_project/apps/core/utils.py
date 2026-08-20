from pakpos_project.apps.core.models import SystemSetting

# Hardcoded Default Settings for PakPOS Branding
DEFAULT_SETTINGS = {
    "APP_NAME": "PakPOS",
    "APP_SUBTITLE": "Professional Point of Sale",
    "APP_CURRENCY": "PKR",
    "APP_FOOTER_TEXT": "Powered by PakPOS",
    "APP_PRIMARY_COLOR": "#2563eb",
    "PRODUCTS_PER_PAGE": "50",
    "POS_DEFAULT_DISCOUNT_PERCENT": "0.0",
    "POS_DEFAULT_TAX_PERCENT": "0.0",
    "POS_DEFAULT_SERVICE_CHARGE_PERCENT": "0.0",
    "POS_DEFAULT_DELIVERY_CHARGES": "0.0",
    "POS_OPERATION_MODE": "restaurant",
    "POS_SHIFT_START_HOUR": "0",
    "POS_SHIFT_END_HOUR": "23",
    "POS_AUTO_APPLY_DISCOUNT": "False",
    "OWNER_EMAIL_1": "",
    "OWNER_EMAIL_2": "",
    "OWNER_EMAIL_3": ""
}

def get_setting(key, fallback=None):
    """
    Fetches a setting from the SystemSetting database.
    If it doesn't exist, it creates it using the DEFAULT_SETTINGS.
    """
    try:
        # Check if the setting exists in the database
        setting = SystemSetting.objects.get(key=key)
        return setting.value
    except SystemSetting.DoesNotExist:
        # If it doesn't exist, create it using the PakPOS default
        default_val = DEFAULT_SETTINGS.get(key, fallback if fallback is not None else "")
        try:
            SystemSetting.objects.create(key=key, value=default_val, is_synced=False)
        except Exception:
            pass # Handle potential race conditions
        return default_val
