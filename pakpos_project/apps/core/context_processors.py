from django.conf import settings


def branding(request):
    """
    Inject global branding and system configuration from settings (.env) into all templates
    """
    return {
        'APP_NAME': getattr(settings, 'APP_NAME', 'PakPOS'),
        'APP_SUBTITLE': getattr(settings, 'APP_SUBTITLE', 'Management Portal'),
        'APP_CURRENCY': getattr(settings, 'APP_CURRENCY', 'PKR'),
        'APP_FOOTER_TEXT': getattr(settings, 'APP_FOOTER_TEXT', 'PakPOS — Modern Point of Sale System.'),
        'APP_PRIMARY_COLOR': getattr(settings, 'APP_PRIMARY_COLOR', '#2563eb'),
        'PRODUCTS_PER_PAGE': getattr(settings, 'PRODUCTS_PER_PAGE', 50),
        'SESSION_COOKIE_AGE_DAYS': getattr(settings, 'SESSION_COOKIE_AGE_DAYS', 30),
        'POS_DEFAULT_TAX_PERCENT': getattr(settings, 'POS_DEFAULT_TAX_PERCENT', 0),
        'POS_DEFAULT_SERVICE_CHARGE_PERCENT': getattr(settings, 'POS_DEFAULT_SERVICE_CHARGE_PERCENT', 0),
        'POS_DEFAULT_DISCOUNT_PERCENT': getattr(settings, 'POS_DEFAULT_DISCOUNT_PERCENT', 0),
        'POS_AUTO_APPLY_DISCOUNT': getattr(settings, 'POS_AUTO_APPLY_DISCOUNT', False),
        'POS_DEFAULT_DELIVERY_CHARGES': getattr(settings, 'POS_DEFAULT_DELIVERY_CHARGES', 150),
        'POS_OPERATION_MODE': getattr(settings, 'POS_OPERATION_MODE', 'retail'),
    }

