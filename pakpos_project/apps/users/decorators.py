from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()


def role_required(*allowed_roles):
    """
    Decorator to restrict view access to users with specific roles.
    Admins / Superusers are automatically permitted.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to access this page.')
                return redirect('users:login')
                
            if not request.user.is_active:
                messages.error(request, 'Your account has been deactivated. Please contact your administrator.')
                return redirect('users:login')

            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(request, 'You do not have permission to access this page.')
            return redirect(request.user.get_redirect_url())
            
        return _wrapped_view
    return decorator


def admin_required(view_func):
    """
    Shortcut decorator for views requiring Admin role
    """
    return role_required(User.Role.ADMIN)(view_func)


def manager_or_admin_required(view_func):
    """
    Backward-compatible alias for admin_required
    """
    return role_required(User.Role.ADMIN)(view_func)

