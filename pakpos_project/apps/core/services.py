import os
from pathlib import Path
from django.conf import settings
from dotenv import load_dotenv


def get_current_system_settings():
    """
    Reads the current settings from .env file and active runtime config.
    """
    env_path = settings.BASE_DIR / '.env'
    if env_path.exists():
        load_dotenv(env_path, override=True)

    return {
        'app_name': os.getenv('APP_NAME', getattr(settings, 'APP_NAME', 'PakPOS')),
        'app_subtitle': os.getenv('APP_SUBTITLE', getattr(settings, 'APP_SUBTITLE', 'Management Portal')),
        'app_currency': os.getenv('APP_CURRENCY', getattr(settings, 'APP_CURRENCY', 'PKR')),
        'app_footer_text': os.getenv('APP_FOOTER_TEXT', getattr(settings, 'APP_FOOTER_TEXT', 'PakPOS — Modern Point of Sale System.')),
        'time_zone': os.getenv('TIME_ZONE', getattr(settings, 'TIME_ZONE', 'Asia/Karachi')),
        'pos_operation_mode': os.getenv('POS_OPERATION_MODE', getattr(settings, 'POS_OPERATION_MODE', 'restaurant')),
        'pos_default_tax_percent': float(os.getenv('POS_DEFAULT_TAX_PERCENT', getattr(settings, 'POS_DEFAULT_TAX_PERCENT', 0))),
        'pos_default_service_charge_percent': float(os.getenv('POS_DEFAULT_SERVICE_CHARGE_PERCENT', getattr(settings, 'POS_DEFAULT_SERVICE_CHARGE_PERCENT', 0))),
        'pos_default_discount_percent': float(os.getenv('POS_DEFAULT_DISCOUNT_PERCENT', getattr(settings, 'POS_DEFAULT_DISCOUNT_PERCENT', 0))),
        'pos_auto_apply_discount': os.getenv('POS_AUTO_APPLY_DISCOUNT', str(getattr(settings, 'POS_AUTO_APPLY_DISCOUNT', False))).lower() in ('true', '1', 't'),
        'pos_default_delivery_charges': float(os.getenv('POS_DEFAULT_DELIVERY_CHARGES', getattr(settings, 'POS_DEFAULT_DELIVERY_CHARGES', 150))),
        'pos_shift_start_hour': int(os.getenv('POS_SHIFT_START_HOUR', getattr(settings, 'POS_SHIFT_START_HOUR', 9))),
        'pos_shift_end_hour': int(os.getenv('POS_SHIFT_END_HOUR', getattr(settings, 'POS_SHIFT_END_HOUR', 23))),
        'products_per_page': int(os.getenv('PRODUCTS_PER_PAGE', getattr(settings, 'PRODUCTS_PER_PAGE', 50))),
        'session_cookie_age_days': int(os.getenv('SESSION_COOKIE_AGE_DAYS', getattr(settings, 'SESSION_COOKIE_AGE_DAYS', 30))),
    }


def save_system_settings(cleaned_data):
    """
    Safely saves updated settings into .env file and updates runtime Django settings.
    """
    env_path = settings.BASE_DIR / '.env'
    if not env_path.exists():
        example_path = settings.BASE_DIR / '.env.example'
        if example_path.exists():
            import shutil
            shutil.copy(example_path, env_path)
        else:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write("# Django Settings\n")

    # Map form field names to .env uppercase keys
    mapping = {
        'app_name': 'APP_NAME',
        'app_subtitle': 'APP_SUBTITLE',
        'app_currency': 'APP_CURRENCY',
        'app_footer_text': 'APP_FOOTER_TEXT',
        'time_zone': 'TIME_ZONE',
        'pos_operation_mode': 'POS_OPERATION_MODE',
        'pos_default_tax_percent': 'POS_DEFAULT_TAX_PERCENT',
        'pos_default_service_charge_percent': 'POS_DEFAULT_SERVICE_CHARGE_PERCENT',
        'pos_default_discount_percent': 'POS_DEFAULT_DISCOUNT_PERCENT',
        'pos_auto_apply_discount': 'POS_AUTO_APPLY_DISCOUNT',
        'pos_default_delivery_charges': 'POS_DEFAULT_DELIVERY_CHARGES',
        'pos_shift_start_hour': 'POS_SHIFT_START_HOUR',
        'pos_shift_end_hour': 'POS_SHIFT_END_HOUR',
        'products_per_page': 'PRODUCTS_PER_PAGE',
        'session_cookie_age_days': 'SESSION_COOKIE_AGE_DAYS',
    }

    env_updates = {}
    for form_key, env_key in mapping.items():
        if form_key in cleaned_data and cleaned_data[form_key] is not None:
            env_updates[env_key] = str(cleaned_data[form_key]).strip()

    lines = []
    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in line:
            key = line.split('=', 1)[0].strip()
            if key in env_updates:
                new_lines.append(f"{key}={env_updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for key, val in env_updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    # Reload into runtime
    load_dotenv(env_path, override=True)

    for env_key, val in env_updates.items():
        if hasattr(settings, env_key):
            curr_val = getattr(settings, env_key)
            if isinstance(curr_val, bool):
                setattr(settings, env_key, str(val).lower() in ('true', '1', 't'))
            elif isinstance(curr_val, int):
                try:
                    setattr(settings, env_key, int(float(val)))
                except (ValueError, TypeError):
                    setattr(settings, env_key, 0)
            elif isinstance(curr_val, float):
                try:
                    setattr(settings, env_key, float(val))
                except (ValueError, TypeError):
                    setattr(settings, env_key, 0.0)
            else:
                setattr(settings, env_key, str(val))
