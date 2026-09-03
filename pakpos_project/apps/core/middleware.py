import traceback
from django.utils.deprecation import MiddlewareMixin
from pakpos_project.apps.core.logger import log_system_error
from django.utils import timezone
import zoneinfo
from pakpos_project.apps.core.models import SystemSetting

class TimezoneMiddleware(MiddlewareMixin):
    """
    Middleware that globally activates the timezone chosen by the user in System Settings.
    """
    def process_request(self, request):
        try:
            setting = SystemSetting.objects.get(pk=1)
            if setting.time_zone:
                timezone.activate(zoneinfo.ZoneInfo(setting.time_zone))
            else:
                timezone.deactivate()
        except Exception:
            timezone.deactivate()

class ExceptionLoggingMiddleware(MiddlewareMixin):
    """
    Middleware that catches unhandled exceptions and all 400/500 HTTP errors
    and logs them to the local system_logs.json file for Google Sheets synchronization.
    """
    def process_exception(self, request, exception):
        # Log unhandled 500 Internal Server Errors with full traceback
        error_msg = f"Unhandled Exception at {request.path}: {str(exception)}\n{traceback.format_exc()}"
        log_system_error("WebServerError (500)", error_msg)
        return None  # Let Django continue its normal error handling

    def process_response(self, request, response):
        # Ignore static, media, and background polling endpoints to prevent spamming the logs
        if request.path.startswith('/static/') or request.path.startswith('/media/') or request.path == '/api/payment-alert/':
            return response
            
        # Log HTTP requests
        if response.status_code >= 400:
            error_msg = f"HTTP {response.status_code} Error at {request.path} ({request.method})"
            log_system_error(f"HTTP Error ({response.status_code})", error_msg)
        else:
            msg = f"HTTP {response.status_code} Success at {request.path} ({request.method})"
            log_system_error("HTTPRequest", msg)
            
        return response
