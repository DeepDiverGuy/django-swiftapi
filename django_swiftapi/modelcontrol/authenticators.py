from django.http import HttpRequest
from django.db.models import Model
from ninja_extra import permissions
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from allauth.headless.account.views import SessionView



class ReadOnly(permissions.BasePermission):
    """
    be careful using this permission class! this means all "GET", "HEAD", "OPTIONS" requests will pass.
    """
    def has_permission(self, request:HttpRequest, view):
        return request.method in permissions.SAFE_METHODS

class base_UserAuthentication(permissions.BasePermission):
    """
    allows access only to authenticated users.
    inherit this class and override `has_permission()` & `has_object_permission()` to use with your own authentication system. `has_permission()` should return the authenticated user.
    """

    def __init__(self, extra_permission_list=[], *args, **kwargs):
        self.extra_permission_list = extra_permission_list
        super().__init__(*args, **kwargs)
    
    def has_permission(self, request: HttpRequest, *args, **kwargs):
        user = request.user if request.user and request.user.is_authenticated else None
        return user
    
    def has_object_permission(self, request:HttpRequest, obj, *args, **kwargs) -> bool:
        """
        this is used to check if the user has permission to access the object.
        if the object has `created_by_field` specified, it will check if the requesting user is the one who created it, returns false otherwise. however, if the object doesn't have `created_by_field` specified, it will return False.
        """
        if obj:
            the_user = getattr(obj, obj.created_by_field)
            return the_user == request.user
        return False

    @classmethod
    async def has_object_permission_custom(cls, request:HttpRequest, model:Model, id, *args, **kwargs) -> bool:
        obj = await model.objects.filter(id=id).select_related(model.created_by_field).afirst()
        if obj:
            the_user = getattr(obj, model.created_by_field)
            return the_user == request.user
        return False

class get_user_from_allauth_sessionview(SessionView):
    def dispatch(self, request, *args, **kwargs):
        return request.user
    
def get_user_from_allauth(client, request): # client is either 'app' or 'browser', according to allauth
    try:
        return get_user_from_allauth_sessionview.as_api_view(client=client)(request)
    except:
        pass

def djangoallauth_authenticator(request, client='app', extra_permission_list=[]):
    """
    extra_permission_list takes user model's boolean field_names in str format to check if these are true. If true, then pass. If the field_name does not exist, then validation won't pass.
    """
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

class djangoallauth_UserAuthentication(base_UserAuthentication):
    '''
    ::USAGE::
    - to use with route (example): `djangoallauth_UserAuthentication(extra_permission_list=["is_owner", "is_vendor"])`. `is_owner` & `is_vendor` are boolean fields of the `settings.AUTH_USER_MODEL` model. can be anything specified as boolean in the model

    - to check object permission from an user-defined modelcontroller view: `self.check_object_permissions(request, obj=instance)`. `obj=instance` is any django model's instance that has `created_by_field` specified to check if the user trying to access the route is the one who created it
    '''

    def has_permission(self, request:HttpRequest, *args, **kwargs):
        """
        this is used to check if the user is logged in.
        if the user is logged in, it will return the `User` object. `None` otherwise.
        """
        return djangoallauth_authenticator(request, extra_permission_list=self.extra_permission_list)
            
