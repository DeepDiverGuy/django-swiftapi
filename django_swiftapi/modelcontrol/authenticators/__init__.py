from .base import BaseUserAuthentication

__all__ = ["BaseUserAuthentication", "djangoallauth_authenticator"]

def __getattr__(name):
    if name == "djangoallauth_authenticator":
        try:
            from .django_allauth import djangoallauth_authenticator
            return djangoallauth_authenticator
        except ImportError as e:
            raise ImportError(
                "djangoallauth_authenticator requires 'django-allauth'. "
                "Install it using 'pip install django-allauth'."
            ) from e
    raise AttributeError(f"module {__name__} has no attribute {name}")
