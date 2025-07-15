from typing import Iterable
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import models
from django_swiftapi.crud_operation.file_operations.files_handlers import Files_Param



User = getattr(settings, 'AUTH_USER_MODEL', None)
FilesParam = Files_Param

class SwiftBaseModel(models.Model):
    """
    INFO:
    the specification of this model automatically takes effect while using `crud_operation.core.crud_handler` or `modelcontrol.base_modelcontrollers.SwiftBaseModelController` when it's using default settings.


    Example usage:

    - these two requirements below only only take effect when we are using `crud_handler`
        required_to_create = []
        required_to_update = []

    - these excludes below apply while creating schemas
        exclude_in_request = []
        exclude_in_response = []

    - object_owner:
        -  obj_owner_check_before_save: if `True`, it will check if the requesting user is the creator of the object before saving.
        - obj_fields_to_check_owner: fields to check if the requesting user is the creator of the objects in those fields before saving.

    - if you are using another field for checking owner, specify it here
        created_by_field = ""  # default is 'created_by'

    - file-field example:
        - specify your file-fields like this: `field_name = ArrayField(models.CharField(max_length=200), default=list, size=1, blank=True, null=True)`, size means maximum allowed number of files, you can specify it as per your need

        - then, tell django-swiftapi about which ones are the file-fields like this: `files_fields = []`

        - then, configure the file settings in the list:
            `
            files_params_list = [
                FilesParam(
                    field_name="your_arrayfield_variable",
                    access = "public",
                    storage=<storage_class>,
                    validator_funcs={
                        "file_sizes_valid": {
                            "limit": 10,
                        },
                        "images_valid": {},
                    },
                ),
                FilesParam(
                    field_name="your_arrayfield_variable",
                    access = "private",
                    storage=<storage_class>,
                    validator_funcs={
                        "file_sizes_valid": {
                            "limit": 20,
                        },
                        "images_valid": {},
                    },
                ),
            ]
        `
    """

    created = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated = models.DateTimeField(auto_now=True, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, default=None)

    created_by_field:str = 'created_by'

    required_to_create:list[str] = []
    required_to_update:list[str] = []

    exclude_in_request:list[str] = ['id', 'created', 'updated', 'created_by']
    exclude_in_response:list[str] = []

    files_fields:list[str] = []
    files_params_list:list = []

    obj_owner_check_before_save:bool = False
    obj_fields_to_check_owner:list[str] = []

    def save(
        self,
        *args,
        request=None,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None,
    ):
        """
        added support for accepting `request` as an argument
        """
        return super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)

    async def asave(
        self,
        *args,
        request=None,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None,
    ):
        """
        added support for accepting `request` as an argument
        """
        if args:
            force_insert, force_update, using, update_fields = self._parse_params(
                *args,
                method_name="asave",
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            )
        return await sync_to_async(self.save)(
            *args,
            request=request,
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
    
    def __str__(self):
        return str(self.id)
    
    # @classmethod
    # def files_fields(cls):
    #     return [param.field_name for param in cls.files_params_list] if cls.files_params_list else []
    
    class Meta:
        abstract = True
        ordering = ['-id']

