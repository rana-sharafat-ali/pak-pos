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
        'PRODUCTS_PER_PAGE': getattr(settings, 'PRODUCTS_PER_PAGE', 50),
        'SESSION_COOKIE_AGE_DAYS': getattr(settings, 'SESSION_COOKIE_AGE_DAYS', 30),
    }
