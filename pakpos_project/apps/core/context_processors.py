from pakpos_project.apps.core.models import SystemSetting, PaymentAlert

def branding(request):
    """
    Inject global branding, system configuration, and Payment Alert from Singleton Database into all templates
    """
    settings = SystemSetting.load()
    payment_alert = PaymentAlert.load()
    return {
        'APP_NAME': settings.app_name,
        'APP_SUBTITLE': settings.app_subtitle,
        'APP_CURRENCY': settings.app_currency,
        'APP_FOOTER_TEXT': settings.app_footer_text,
        'APP_PRIMARY_COLOR': settings.app_primary_color,
        'PRODUCTS_PER_PAGE': settings.products_per_page,
        'POS_DEFAULT_TAX_PERCENT': settings.pos_default_tax_percent,
        'POS_DEFAULT_SERVICE_CHARGE_PERCENT': settings.pos_default_service_charge_percent,
        'POS_DEFAULT_DISCOUNT_PERCENT': settings.pos_default_discount_percent,
        'POS_AUTO_APPLY_DISCOUNT': settings.pos_auto_apply_discount,
        'POS_DEFAULT_DELIVERY_CHARGES': settings.pos_default_delivery_charges,
        'POS_OPERATION_MODE': settings.pos_operation_mode,
        'PAYMENT_ALERT': payment_alert,
    }

