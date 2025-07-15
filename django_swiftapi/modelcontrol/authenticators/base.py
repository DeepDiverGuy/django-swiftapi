from django.http import HttpRequest
from django.db.models import Model
from ninja_extra import permissions



class ReadOnly(permissions.BasePermission):
    """
    be careful using this permission class.
    this means all "GET", "HEAD", "OPTIONS" requests will pass.
    """
    def has_permission(self, request:HttpRequest, view):
        return request.method in permissions.SAFE_METHODS


class BaseUserAuthentication(permissions.BasePermission):
    """
    Base permission class that restricts access to authenticated users only.

    This class is intended to be inherited by other permission classes where
    authentication and authorization logic needs to be customized.

    - `has_permission()` checks whether the request has an authenticated user.
      It should be overridden to apply custom authentication logic.
    - `has_object_permission()` enforces object-level access by checking
      if the authenticated user matches the object's `created_by_field`.

    Attributes:
        extra_permission_list (list): Optional list of additional permission flags
        that can be used in extended classes. these are boolean fields of the 
        `settings.AUTH_USER_MODEL` model. can be anything specified as boolean in the model

    Example:
        class CustomAuth(BaseUserAuthentication):
            def has_permission(self, request, *args, **kwargs):
                # your custom logic here
    """

    def __init__(self, extra_permission_list=[], *args, **kwargs):
        """
        Initializes the permission class.

        Args:
            extra_permission_list (list): Optional list of additional permission checks.
            *args, **kwargs: Additional arguments for the parent class.
        """
        self.extra_permission_list = extra_permission_list
        super().__init__(*args, **kwargs)

    def has_permission(self, request: HttpRequest, *args, **kwargs):
        """
        Checks if the request has a valid authenticated user.

        This method can be overridden in subclasses to implement custom logic
        (e.g., role-based or token-based authentication).

        Args:
            request (HttpRequest): The incoming HTTP request.
            *args, **kwargs: Additional arguments.

        Returns:
            User | None: The authenticated user if valid, else None.
        """
        user = request.user if request.user and request.user.is_authenticated else None
        return user

    def has_object_permission(self, request: HttpRequest, obj, *args, **kwargs) -> bool:
        """
        Checks if the authenticated user has permission to access the given object.

        This method looks for an attribute on the object defined by `created_by_field`,
        and compares it to the requesting user. normally, it's used as 
        `self.has_object_permission(request, obj)` in the context of django-ninja-extra.

        Args:
            request (HttpRequest): The incoming HTTP request.
            obj (Any): The object being accessed.
            *args, **kwargs: Additional arguments.

        Returns:
            bool: True if the user is allowed to access the object, False otherwise.

        Note:
            - The object must define `created_by_field` (e.g., `"created_by"`) as a class attribute.
            - If the field does not exist or does not match the request.user, returns False.
        """
        if obj:
            the_user = getattr(obj, obj.created_by_field, None)
            return the_user == request.user
        return False


    @classmethod
    async def has_object_permission_custom(cls, request:HttpRequest, model:Model, id, *args, **kwargs) -> bool:
        obj = await model.objects.filter(id=id).select_related(model.created_by_field).afirst()
        if obj:
            the_user = getattr(obj, model.created_by_field)
            return the_user == request.user
        return False

