from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend allowing login via either Username OR Email (case-insensitive).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username_or_email') or kwargs.get('email')
            
        if not username or not password:
            return None

        username = username.strip()
        
        try:
            # Query case-insensitively for either username or email
            user = User.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).first()
            
            if user and user.check_password(password):
                return user
        except Exception:
            return None

        return None
