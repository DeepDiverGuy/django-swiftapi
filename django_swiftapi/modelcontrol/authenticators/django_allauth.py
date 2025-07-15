from django.http import HttpRequest
from django.contrib.auth.models import AnonymousUser
from allauth.headless.account.views import SessionView
from django_swiftapi.modelcontrol.authenticators.base import BaseUserAuthentication



class get_user_from_allauth_sessionview(SessionView):
    def dispatch(self, request, *args, **kwargs):
        return request.user
    
def get_user_from_allauth(client, request): # client is either 'app' or 'browser', according to allauth
    try:
        return get_user_from_allauth_sessionview.as_api_view(client=client)(request)
    except:
        pass

def djangoallauth_authenticator(request, client='app', extra_permission_list=[]):
    try:
        user = get_user_from_allauth(client, request)
        if isinstance(user, AnonymousUser) or user=='AnonymousUser':
            return None
        if not user.is_active:
            return None
        if extra_permission_list:
            for extra_permission in extra_permission_list:
                if not getattr(user, extra_permission):
                    return None
        return user
    except:
        return None


class djangoallauth_userauthentication(BaseUserAuthentication):
    """
    Authentication class using Django AllAuth-based logic with optional extra user permissions.

    This class extends `BaseUserAuthentication` to provide route-level and object-level
    permission handling for authenticated users, with optional permission flags
    mapped to boolean fields on the user model.

    Usage:
        1. With route-level permissions:
            >>> djangoallauth_userauthentication(extra_permission_list=["is_owner", "is_vendor"])
            This will only allow access to users where both `is_owner` and `is_vendor` fields
            on the `settings.AUTH_USER_MODEL` instance are `True`.

        2. With object-level permissions (inside a custom view/controller):
            >>> self.check_object_permissions(request, obj=instance)
            `instance` must have a `created_by_field` attribute set to check
            if the requesting user is the creator of the object.

    Args:
        extra_permission_list (list): Optional list of user model boolean fields that
        must be `True` for access to be granted.
    """

    def has_permission(self, request: HttpRequest, *args, **kwargs):
        """
        Checks if the user is authenticated and meets extra permission criteria.

        This method is typically called automatically by DRF when evaluating access
        to a route. It uses `djangoallauth_authenticator` to authenticate the user
        and validate that any specified extra permission flags are satisfied.

        Args:
            request (HttpRequest): The incoming request containing the user object.
            *args, **kwargs: Optional additional arguments.

        Returns:
            User | None: Returns the authenticated user if permission checks pass;
            otherwise returns None.
        """
        return djangoallauth_authenticator(request, extra_permission_list=self.extra_permission_list)

