from django.db.models import Model
from ninja.pagination import paginate
from ninja import Schema
from ninja_extra import (
    ModelControllerBase,
    ModelService,
    http_get,
    http_post, 
    http_delete
)
from django_swiftapi.dynamic_environment import run_new_environment
from django_swiftapi.modelcontrol.schemas.base import schema_generator, filterschema_generator
from django_swiftapi.crud_operation.core import crud_handler


# Example Decorator below
# @api_controller("/something", permissions=[])
class SwiftBaseModelController(ModelControllerBase):
    """
    A customizable base-modelcontroller for handling CRUD operations on `SwiftBaseModel`.

    Extend this class to enable fine-grained control over API endpoints, request/response schemas,
    permission checks.

    Attributes:
        operation_handler (callable): Handler responsible for performing the CRUD logic. Default is `crud_handler`.
        model_to_control (Model): Django model class to be managed by the controller.

        # ignore these `premium` attributes below. these are not implemented yet.
        premium_checker (Optional[class]): Custom class for validating premium access.
        product_type (Optional[str]): Internal product plan type used in premium validation.
        product_asset_model (Optional[Model]): Asset model associated with the product.
        parent_field_name (Optional[str]): Field name linking to the parent model, used for `max_add` logic.

    Supported Operations (flags below enable/disable each route):
        - create_enabled: POST route to create a new model instance.
        - retrieve_one_enabled: GET route to retrieve a single item.
        - filter_enabled: GET route with filtering and search.
        - update_enabled: PATCH/PUT route to update existing items.
        - file_retrieve_enabled: GET route to retrieve a specific file of an item.
        - files_remove_enabled: POST/DELETE route to remove files from an item.
        - delete_enabled: DELETE route to remove an item and its files.

    Request/Response Customization:
        - Each operation supports `*_request_schemas` and `*_response_schemas` for overriding default schemas.
        - Request schemas use: `[('body', 'body_schema', SchemaClass, required:bool)]`
        - Response schemas use: `{status_code: SchemaClass}`

    Permission Control:
        - `*_custom_permissions_list`: List of permission classes (e.g., [permissions.AllowAny]).
          If empty list (`[]`), defaults to `@api_controller` permissions.
        - `*_obj_permission_check`: If True, checks if `obj.created_by_field == request.user`.
        
        # ignore this attribute below. this is not implemented yet.
        - `*_premium_check`: If True, validates if the user's payment plan is eligible.

    Note:
        This class is designed to work with the `@api_controller` decorator.
    """

    operation_handler = crud_handler

    model_to_control: Model

    # ignore anything referred to as "premium", this is not implemented yet
    premium_checker = None
    product_type: str = None
    product_asset_model: Model = None
    parent_field_name: str = None  # string representing the connector field to the parent model (important for checking max_add)

    create_enabled: bool = False
    create_path: str = 'create'
    create_info: str = 'create an item'
    create_request_schemas: list[tuple[str, str, Schema, bool]] = None
    create_response_schemas: dict[int, Schema] = None
    create_custom_permissions_list: list = []
    create_premium_check: bool = False

    retrieve_one_enabled: bool = False
    retrieve_one_path: str = 'retrieveone/{id}'
    retrieve_one_info: str = 'retrieve an item'
    retrieve_one_depth = 0
    retrieve_one_response_schemas: dict[int, Schema] = None
    retrieve_one_custom_permissions_list: list = []
    retrieve_one_obj_permission_check: bool = False
    retrieve_one_premium_check: bool = False

    filter_enabled: bool = False
    filter_path: str = 'filter'
    filter_info: str = 'filter & get the listed result'
    filter_depth = 0
    filter_request_schemas: list[tuple[str, str, Schema, bool]] = None
    filter_response_schemas: dict[int, Schema] = None
    filter_custom_permissions_list: list = []
    filter_obj_permission_check: bool = False
    filter_premium_check: bool = False

    update_enabled: bool = False
    update_path: str = '{id}/update'
    update_info: str = 'update or add files to an item'
    update_request_schemas: list[tuple[str, str, Schema, bool]] = None
    update_response_schemas: dict[int, Schema] = None
    update_custom_permissions_list: list = []
    update_obj_permission_check: bool = False
    update_premium_check: bool = False

    file_retrieve_enabled: bool = False
    file_retrieve_path: str = '{id}/file/retrieve'
    file_retrieve_info: str = 'retrieve a single file of an item'
    file_retrieve_request_schemas: list[tuple[str, str, Schema, bool]] = None
    file_retrieve_response_schemas: dict[int, Schema] = None
    file_retrieve_custom_permissions_list: list = []
    file_retrieve_obj_permission_check: bool = False
    file_retrieve_premium_check: bool = False

    files_remove_enabled: bool = False
    files_remove_path: str = '{id}/files/remove'
    files_remove_info: str = 'remove files of an item', 
    files_remove_request_schemas: list[tuple[str, str, Schema, bool]] = None
    files_remove_response_schemas: dict[int, Schema] = None
    files_remove_custom_permissions_list: list = []
    files_remove_obj_permission_check: bool = False
    files_remove_premium_check: bool = False

    delete_enabled: bool = False
    delete_path: str = '{id}/delete'
    delete_info: str = 'delete an item with all its files'
    delete_response_schemas: dict[int, Schema] = None
    delete_custom_permissions_list: list = []
    delete_obj_permission_check: bool = False
    delete_premium_check: bool = False


    def __init__(self):
        self.model_service = ModelService(model=self.model_to_control)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if cls.create_enabled:
            create_request_schemas = cls.create_request_schemas or schema_generator(model=cls.model_to_control, schema_type='request', action="create", files_fields_only=False)
            # create_response_schemas = cls.create_response_schemas or schema_generator(model=cls.model_to_control, schema_type='response', action="create", files_fields_only=False, custom_depth=0)
            create_response_schemas = cls.create_response_schemas or cls.operation_handler.CU_response_schema(model=cls.model_to_control, action='C')

            create_func_name = 'create'
            create_extra_globals={'cls': cls,}
            create_args = "*args, request, "
            create_schema_names = ""
            for name, annot_name, annot_cls, required in create_request_schemas: # index, (name, annot_name, annot_cls, required) in enumerate(create_request_schemas):
                create_args += f"{name}: {annot_name}=None, " if not required else f"{name}: {annot_name}, "
                create_extra_globals[f"{annot_name}"] = annot_cls
                create_schema_names += f"'{name}', "
            create_codes = f"""
import inspect

async def {create_func_name}({create_args}):
    frame = inspect.currentframe()
    local_args = inspect.getargvalues(frame).locals

    schema_names = [{create_schema_names}]
    request_body = {{}}
    for schema_name in schema_names:
        request_body[f"{{schema_name}}"] = local_args.get(f"{{schema_name}}")

    model_to_control = cls.model_to_control
    handler = cls.operation_handler(request=request, model=model_to_control, request_body=request_body, premium_check=cls.create_premium_check, premium_checker=cls.premium_checker, product_type=cls.product_type, product_asset_model=cls.product_asset_model, parent_field_name=cls.parent_field_name)
    return await handler.save_files_or_instance(create=True, ninja_response=True,)
"""

            create_func = run_new_environment(create_func_name, create_codes, extra_globals=create_extra_globals)
            create_api_view = http_post(f"/{cls.create_path}", summary=cls.create_info, permissions=cls.create_custom_permissions_list or None, response=create_response_schemas, )(create_func)

            cls.create = create_api_view

        if cls.retrieve_one_enabled:
            # no schema needed for retrieve_one-request of an object
            # retrieve_one_response_schemas = cls.retrieve_one_response_schemas or cls.operation_handler.RO_response_schema(model=cls.model_to_control)
            retrieve_one_response_schemas = cls.retrieve_one_response_schemas or schema_generator(model=cls.model_to_control, schema_type='response', action='retrieve', custom_depth=cls.retrieve_one_depth, )

            retrieve_one_func_name = 'retrieve_one'
            retrieve_one_extra_globals={'cls': cls,}
            retrieve_one_args = "*args, request, id, "
            retrieve_one_codes = f"""
# from ninja.responses import Response

async def {retrieve_one_func_name}({retrieve_one_args}):
    model_to_control = cls.model_to_control
    handler = cls.operation_handler(request=request, model=model_to_control, id=id, object_permission_check=cls.retrieve_one_obj_permission_check, premium_check=cls.retrieve_one_premium_check, premium_checker=cls.premium_checker, product_type=cls.product_type, product_asset_model=cls.product_asset_model, parent_field_name=cls.parent_field_name)
    return await handler.retrieve_instance(ninja_response=True,)
"""

            retrieve_one_func = run_new_environment(retrieve_one_func_name, retrieve_one_codes, extra_globals=retrieve_one_extra_globals)
            retrieve_one_api_view = http_get(f"{cls.retrieve_one_path}", summary=cls.retrieve_one_info, permissions=cls.retrieve_one_custom_permissions_list or None, response=retrieve_one_response_schemas)(retrieve_one_func)
        
            cls.retrieve_one = retrieve_one_api_view

        if cls.update_enabled:
            update_request_schemas = cls.update_request_schemas or schema_generator(model=cls.model_to_control, schema_type='request', action="update", files_fields_only=False)
            # update_response_schemas = cls.update_response_schemas or schema_generator(model=cls.model_to_control, schema_type='response', action="update", files_fields_only=False, custom_depth=0)
            update_response_schemas = cls.update_response_schemas or cls.operation_handler.CU_response_schema(model=cls.model_to_control, action='U')

            update_func_name = 'update'
            update_extra_globals={'cls': cls,}
            update_args = "*args, request, id, "
            update_schema_names = ""
            for name, annot_name, annot_cls, required in update_request_schemas: # index, (name, annot_name, annot_cls, required) in enumerate(update_request_schemas):
                update_args += f"{name}: {annot_name}=None, " if not required else f"{name}: {annot_name}, "
                update_extra_globals[f"{annot_name}"] = annot_cls
                update_schema_names += f"'{name}', "
            update_codes = f"""
import inspect
# from ninja.responses import Response

async def {update_func_name}({update_args}):
    frame = inspect.currentframe()
    local_args = inspect.getargvalues(frame).locals

    schema_names = [{update_schema_names}]
    request_body = {{}}
    for schema_name in schema_names:
        request_body[f"{{schema_name}}"] = local_args.get(f"{{schema_name}}")

    model_to_control = cls.model_to_control
    handler = cls.operation_handler(request=request, model=model_to_control, id=id, request_body=request_body, object_permission_check=cls.update_obj_permission_check, premium_check=cls.update_premium_check, premium_checker=cls.premium_checker, product_type=cls.product_type, product_asset_model=cls.product_asset_model, parent_field_name=cls.parent_field_name)
    return await handler.save_files_or_instance(ninja_response=True,)
"""

            update_func = run_new_environment(update_func_name, update_codes, extra_globals=update_extra_globals)
            update_api_view = http_post(f"{cls.update_path}", summary=cls.update_info, permissions=cls.update_custom_permissions_list or None, response=update_response_schemas)(update_func)

            cls.update = update_api_view

        if cls.filter_enabled:
            filter_request_schemas = cls.filter_request_schemas or filterschema_generator(model=cls.model_to_control)
            # filter_response_schemas = cls.filter_response_schemas or schema_generator(model=cls.model_to_control, schema_type='response', action="filter", files_fields_only=False, custom_depth=0)
            filter_response_schemas = cls.filter_response_schemas or schema_generator(model=cls.model_to_control, schema_type='response', action='filter', custom_depth=cls.filter_depth, )

            filter_func_name = 'filter'
            filter_extra_globals={'cls': cls,}
            filter_args = "*args, request, "
            filter_schema_name = ""
            for name, annot_name, annot_cls, required in filter_request_schemas: # index, (name, annot_name, annot_cls, required) in enumerate(filter_request_schemas):
                filter_args += f"{name}: {annot_name}=None, " if not required else f"{name}: {annot_name}, "
                filter_extra_globals[f"{annot_name}"] = annot_cls
                filter_schema_name = f"{name}"
            filter_codes = f"""
from django.db.models import Q
from ninja.responses import Response

# premium_checker = cls.premium_checker

async def {filter_func_name}({filter_args}):
    model_to_control = cls.model_to_control

    if cls.filter_premium_check:
        premium_checker = cls.premium_checker()
        await premium_checker.initialize(
            product_type=cls.product_type, 
            asset_model=cls.product_asset_model,
            model_to_control=model_to_control,
            request=request
            )
        # for instance in instance_list:
        #     premium_passed, msg = await premium_checker.retrieve_constraints(m_t_c_instance_id=instance.id)
        #     if not premium_passed:
        #         return Response({{"message": msg, "payment_status": premium_checker.payment_status}}, status=401)
        if premium_checker.payment_status == "Payment is due. Service has been cut-off." or premium_checker.payment_status == "N/A":
            return Response({{"payment status": premium_checker.payment_status}}, status=401)

    q = Q(**{{model_to_control.created_by_field: request.user}}) if cls.filter_obj_permission_check else Q()
    q &= {filter_schema_name}.get_filter_expression()
    instance_list = model_to_control.objects.filter(q)
    
    return instance_list
"""

            filter_func = run_new_environment(filter_func_name, filter_codes, extra_globals=filter_extra_globals)
            filter_api_view = paginate()(http_post(f"{cls.filter_path}", summary=cls.filter_info, permissions=cls.filter_custom_permissions_list or None, response=filter_response_schemas)(filter_func))

            cls.filter = filter_api_view

        if cls.file_retrieve_enabled:
            file_retrieve_request_schemas = cls.file_retrieve_request_schemas or schema_generator(model=cls.model_to_control, schema_type='request', action="retrieve", files_fields_only=True)
            # its a file-response, no response schema needed
            # file_retrieve_response_schemas = cls.file_retrieve_response_schemas or schema_generator(model=cls.model_to_control, schema_type='response', action="retrieve", files_fields_only=True, custom_depth=0)

            file_retrieve_func_name = 'file_retrieve'
            file_retrieve_extra_globals={'cls': cls,}
            file_retrieve_args = "*args, request, id, "
            file_retrieve_schema_names = ""
            for name, annot_name, annot_cls, required in file_retrieve_request_schemas: # index, (name, annot_name, annot_cls, required) in enumerate(file_retrieve_request_schemas):
                file_retrieve_args += f"{name}: {annot_name}=None, " if not required else f"{name}: {annot_name}, "
                file_retrieve_extra_globals[f"{annot_name}"] = annot_cls
                file_retrieve_schema_names += f"'{name}', "
            file_retrieve_codes = f"""
import inspect
# from ninja.responses import Response

async def {file_retrieve_func_name}({file_retrieve_args}):
    frame = inspect.currentframe()
    local_args = inspect.getargvalues(frame).locals

    schema_names = [{file_retrieve_schema_names}]
    request_body = {{}}
    for schema_name in schema_names:
        request_body[f"{{schema_name}}"] = local_args.get(f"{{schema_name}}")

    model_to_control = cls.model_to_control
    handler = cls.operation_handler(request=request, model=model_to_control, id=id, request_body=request_body, object_permission_check=cls.file_retrieve_obj_permission_check, premium_check=cls.file_retrieve_premium_check, premium_checker=cls.premium_checker, product_type=cls.product_type, product_asset_model=cls.product_asset_model, parent_field_name=cls.parent_field_name)
    return await handler.file_responder(django_streaming_response=True,)
"""

            file_retrieve_func = run_new_environment(file_retrieve_func_name, file_retrieve_codes, extra_globals=file_retrieve_extra_globals)
            file_retrieve_api_view = http_post(f"{cls.file_retrieve_path}", summary=cls.file_retrieve_info, permissions=cls.file_retrieve_custom_permissions_list or None, )(file_retrieve_func)

            cls.file_retrieve = file_retrieve_api_view
        
        if cls.files_remove_enabled:
            files_remove_request_schemas = cls.files_remove_request_schemas or schema_generator(model=cls.model_to_control, schema_type='request', action="delete", files_fields_only=True)
            files_remove_response_schemas = cls.files_remove_response_schemas or cls.operation_handler.FRemove_response_schema(model=cls.model_to_control)

            files_remove_func_name = 'files_remove'
            files_remove_extra_globals={'cls': cls,}
            files_remove_args = "*args, request, id, "
            files_remove_schema_names = ""
            for name, annot_name, annot_cls, required in files_remove_request_schemas: # index, (name, annot_name, annot_cls, required) in enumerate(files_remove_request_schemas):
                files_remove_args += f"{name}: {annot_name}=None, " if not required else f"{name}: {annot_name}, "
                files_remove_extra_globals[f"{annot_name}"] = annot_cls
                files_remove_schema_names += f"'{name}', "
            
            files_remove_codes = f"""
import inspect
# from ninja.responses import Response

async def {files_remove_func_name}({files_remove_args}):
    frame = inspect.currentframe()
    local_args = inspect.getargvalues(frame).locals

    schema_names = [{files_remove_schema_names}]
    request_body = {{}}
    for schema_name in schema_names:
        request_body[f"{{schema_name}}"] = local_args.get(f"{{schema_name}}")

    model_to_control = cls.model_to_control
    handler = cls.operation_handler(request=request, model=model_to_control, id=id, request_body=request_body, object_permission_check=cls.files_remove_obj_permission_check, premium_check=cls.files_remove_premium_check, premium_checker=cls.premium_checker, product_type=cls.product_type, product_asset_model=cls.product_asset_model, parent_field_name=cls.parent_field_name)
    return await handler.delete_files_or_instance(ninja_response=True,)
"""

            files_remove_func = run_new_environment(files_remove_func_name, files_remove_codes, extra_globals=files_remove_extra_globals)
            files_remove_api_view = http_post(f"{cls.files_remove_path}", summary=cls.files_remove_info, permissions=cls.files_remove_custom_permissions_list or None, response=files_remove_response_schemas)(files_remove_func)
        
            cls.files_remove = files_remove_api_view

        if cls.delete_enabled:
            # no schema needed for delete-request of an object
            delete_response_schemas = cls.delete_response_schemas or cls.operation_handler.D_response_schema(model=cls.model_to_control)

            delete_func_name = 'delete'
            delete_extra_globals={'cls': cls,}
            delete_args = "*args, request, id, "
            delete_codes = f"""
async def {delete_func_name}({delete_args}):
    model_to_control = cls.model_to_control
    handler = cls.operation_handler(request=request, model=model_to_control, id=id, object_permission_check=cls.delete_obj_permission_check, premium_check=cls.delete_premium_check, premium_checker=cls.premium_checker, product_type=cls.product_type, product_asset_model=cls.product_asset_model, parent_field_name=cls.parent_field_name)
    return await handler.delete_files_or_instance(delete_instance=True, ninja_response=True,)
"""

            delete_func = run_new_environment(delete_func_name, delete_codes, extra_globals=delete_extra_globals)
            delete_api_view = http_delete(f"{cls.delete_path}", summary=cls.delete_info, permissions=cls.delete_custom_permissions_list or None, response=delete_response_schemas)(delete_func)
        
            cls.delete = delete_api_view

