from typing import Literal
from django.conf import settings
from django.db import models
from ninja.responses import Response
from ninja import Schema
from django_swiftapi.modelcontrol.authenticators.base import BaseUserAuthentication
from django_swiftapi.crud_operation.file_operations.files_handlers import (
    Config,
    Payload,
    files_upload_handler,
    files_remove_handler,
    files_retrieve_handler,
)
from django_swiftapi.dynamic_environment import run_new_environment


Model = models.Model
default_UserAuthentication = getattr(settings, 'DEFAULT_USER_AUTHENTICATION_CLASS', None) or BaseUserAuthentication

async def instance_maker(action: Literal["create", "retrieve", "update", "delete"], request, model:Model, instance_id:int=0, request_body:dict={}):
    if action=="create":
        instance = model()
        if model.created_by_field:
            try:
                setattr(instance, model.created_by_field, request.user)
            except:
                setattr(instance, model.created_by_field, None)
    else: # elif action=="retrieve" or action=="update" or action=="delete":
        instance = await model.objects.filter(id=instance_id).afirst()
        if instance is None:
            return Response({"message": f"instance with pk={instance_id} not found"}, status=400), None
        
    m2m_fields = []
    if action=="create" or action=="update":
        if action=="create":
            required_fields = model.required_to_create
        elif action=="update":
            required_fields = model.required_to_update
        for required_field in required_fields:
            if not request_body.get(required_field):
                return Response({"message": f"required field missing - {required_field}"}, status=400), None
            
        if model.obj_owner_check_before_save:
            for field_name in model.obj_fields_to_check_owner:
                obj_ids = request_body.get(field_name)
                if not obj_ids:
                    continue
                obj_model = model._meta.get_field(field_name).related_model
                if isinstance(obj_ids, int):
                    obj = await obj_model.objects.filter(id=obj_ids).select_related(obj_model.created_by_field).afirst()
                    if not obj:
                        return Response({"message": f"instance with pk={obj_ids} not found"}, status=400), None
                    if request.user != getattr(obj, obj.created_by_field):
                        return Response({"message": f"permission denied"}, status=400), None
                    request_body[field_name] = obj
                if isinstance(obj_ids, list):
                    manytomany_instances = []
                    for obj_id in obj_ids:
                        obj = await obj_model.objects.filter(id=obj_id).select_related(obj_model.created_by_field).afirst()
                        if not obj:
                            return Response({"message": f"instance with pk={obj_id} not found"}, status=400), None
                        if request.user != getattr(obj, obj.created_by_field):
                            return Response({"message": f"permission denied"}, status=400), None
                        manytomany_instances.append(obj)
                    request_body[field_name] = manytomany_instances
        
        # validating relational fields
        relational_fields = {field.name: field.related_model for field in model._meta.get_fields() if (isinstance(field, models.ForeignKey) or isinstance(field, models.OneToOneField) or isinstance(field, models.ManyToManyField))}
        for field_name, relating_model in relational_fields.items():
            if field_name in model.obj_fields_to_check_owner and model.obj_owner_check_before_save:
                continue
            ids = request_body.get(f"{field_name}")
            if isinstance(ids, int):
                nested_instance = await relating_model.objects.filter(id=ids).afirst()
                if nested_instance is None:
                    return Response({"message": f"invalid value for field '{field_name}': {ids}"}, status=400), None
                request_body[field_name] = nested_instance
            elif isinstance(ids, list):
                manytomany_instances = []
                for each_id in ids:
                    nested_instance = await relating_model.objects.filter(id=each_id).afirst()
                    if nested_instance is None:
                        return Response({"message": f"invalid value for field '{field_name}': {each_id}"}, status=400), None
                    manytomany_instances.append(nested_instance)
                request_body[field_name] = manytomany_instances
        
        files_fields = model.files_fields

        for attr, value in request_body.items():
            if isinstance(instance._meta.get_field(attr), models.ManyToManyField):
                m2m_fields.append((attr, value))
            else:
                if attr in files_fields:
                    continue
                setattr(instance, attr, value)

    return instance, m2m_fields

async def process_request_body(request_body:dict={}):
    new_request_body = {}
    for key, value in request_body.items():
        if isinstance(value, Schema):
            nested_schema_dict = value.dict(exclude_unset=True)
            for k, v in nested_schema_dict.items():
                new_request_body[k] = v
            continue
        if value is not None:
            new_request_body[key] = value
    return new_request_body

async def process_files_params(model:Model, request_body: dict, action: Literal["upload", "remove", "retrieve", "remove_dir"]) -> list:
    files_params_list = model.files_params_list
    
    if action=="remove_dir":
        return files_params_list
    
    result = []
    for param in files_params_list:
        if param.field_name in request_body:
            if action == "upload":
                param.files_uploaded = request_body.get(param.field_name, [])
            elif action in ("remove", "retrieve"):
                param.file_links = request_body.get(param.field_name, [])
            result.append(param)
    
    return result


class crud_handler:
    
    def __init__(self, request, model:Model, id:int=None, request_body:dict={}, object_permission_check:bool=False, premium_checker = None, premium_check:bool=False, product_type:str=None, product_asset_model:Model=None, parent_field_name:str=None):
        self.request = request
        self.model = model
        self.id = id
        self.request_body = request_body
        self.object_permission_check = object_permission_check
        self.premium_checker = premium_checker
        self.premium_check = premium_check
        self.product_type = product_type
        self.product_asset_model = product_asset_model
        self.parent_field_name = parent_field_name
    
    async def object_permitted(self):
        return await default_UserAuthentication.has_object_permission_custom(request=self.request, model=self.model, id=self.id)

    async def save_files_or_instance(self, create=False, ninja_response=True,):
        if self.object_permission_check:
            if not await self.object_permitted():
                return Response({"message": f"permission denied"}, status=400)

        model = self.model
        request = self.request

        request_body = await process_request_body(self.request_body)
        instance, m2m_fields = await instance_maker(
            action='create' if create else 'update',
            request=request,
            model=model, 
            instance_id=None if create else self.id,
            request_body=request_body
        )
        if isinstance(instance, Response):
            return instance
        
        if self.premium_check:
            order_checker = self.premium_checker()
            await order_checker.initialize(
                product_type=self.product_type, 
                asset_model=self.product_asset_model,
                model_to_control=model,
                request=request
            )
            p_f_n = self.parent_field_name
            if create:
                p_id = request_body.get(p_f_n).id if p_f_n else 0
                premium_passed, msg = await order_checker.create_constraints(parent_field_name=p_f_n, parent_id=p_id, create_count=1, )
            else:
                premium_passed, msg = await order_checker.update_constraints()
            if not premium_passed:
                return Response({"message": msg, "payment_status": order_checker.payment_status}, status=401)

        handler = files_upload_handler(
            Payload(
                configs=[
                    Config(
                        create_instance=create,
                        instance=instance, 
                        exclude_in_response=model.exclude_in_response,
                        files_params = await process_files_params(
                            model=model, 
                            request_body=request_body, 
                            action="upload"
                        ),
                        m2m_fields=m2m_fields,
                    ),
                ]
            )
        )

        return await handler.process(ninja_response=ninja_response, request=request)
    
    async def retrieve_instance(self, ninja_response=False,):
        if self.object_permission_check:
            if not await self.object_permitted():
                return Response({"message": f"permission denied"}, status=400)
            
        model = self.model
        request = self.request
        i_id = self.id
            
        instance = await model.objects.filter(id=i_id).afirst()
        if not instance:
            return Response({"message": f"instance with pk={i_id} not found"}, status=400)
            
        if self.premium_check:
            order_checker = self.premium_checker()
            await order_checker.initialize(
                product_type=self.product_type, 
                asset_model=self.product_asset_model,
                model_to_control=model,
                request=request
            )
            premium_passed, msg = await order_checker.retrieve_constraints(m_t_c_instance_id=i_id)
            if not premium_passed:
                return Response({"message": msg, "payment_status": order_checker.payment_status}, status=401)
        return instance

    async def delete_files_or_instance(self, delete_instance=False, ninja_response=True):
        if self.object_permission_check:
            if not await self.object_permitted():
                return Response({"message": f"permission denied"}, status=400)
        
        model = self.model
        request = self.request
        i_id = self.id
            
        instance = await self.model.objects.filter(id=i_id).afirst()
        if not instance:
            return Response({"message": f"instance with pk={i_id} not found"}, status=400)
        
        if self.premium_check:
            order_checker = self.premium_checker()
            await order_checker.initialize(
                product_type=self.product_type, 
                asset_model=self.product_asset_model,
                model_to_control=model,
                request=request
            )
            if delete_instance:
                premium_passed, msg = await order_checker.delete_constraints()
            else:
                premium_passed, msg = await order_checker.update_constraints()
            if not premium_passed:
                return Response({"message": msg, "payment_status": order_checker.payment_status}, status=401)
        
        request_body = await process_request_body(self.request_body)

        handler = files_remove_handler(
            Payload(
                configs=[
                    Config(
                        delete_instance=delete_instance,
                        instance=instance,
                        files_params = await process_files_params(
                            model=self.model, 
                            request_body=request_body, 
                            action="remove" if not delete_instance else "remove_dir"
                        ),
                    ),
                ]
            )
        )

        return await handler.process(ninja_response=ninja_response, request=request)
    
    async def file_responder(self, django_streaming_response=True):
        if self.object_permission_check:
            if not await self.object_permitted():
                return Response({"message": f"permission denied"}, status=400)
        
        model = self.model
        request = self.request
        i_id = self.id
            
        instance = await model.objects.filter(id=i_id).afirst()
        if not instance:
            return Response({"message": f"instance with pk={i_id} not found"}, status=400)
        
        request_body = await process_request_body(self.request_body)
        if not len(request_body)==1 or not len(next(iter(request_body.values())))==1:
            return Response({"message": f"only one file can be retrieved at a time"}, status=400)
        
        if self.premium_check:
            order_checker = self.premium_checker()
            await order_checker.initialize(
                product_type=self.product_type, 
                asset_model=self.product_asset_model,
                model_to_control=model,
                request=request
            )
            premium_passed, msg = await order_checker.retrieve_constraints(m_t_c_instance_id=i_id)
            if not premium_passed:
                return Response({"message": msg, "payment_status": order_checker.payment_status}, status=401)

        handler = files_retrieve_handler(
            Payload(
                configs=[
                    Config(
                        instance=instance,
                        files_params = await process_files_params(
                            model=model, 
                            request_body=request_body, 
                            action="retrieve"
                        ),
                    ),
                ]
            )
        )

        return await handler.process(django_streaming_response=django_streaming_response)


    """
    Some operations of crud_handler needs it's own customized response schemas.
    These methods below are used to generate the response schemas specifically 
    for the operations of crud_handler.
    """
    
    @classmethod
    def CU_response_schema(cls, model: Model, action:Literal['C', 'U']):
        model_name = f"{model._meta.app_label}_{model._meta.model_name}"
        schema_name = f'{model_name}{action}ResponseSchema'
        codes = f"""
from ninja import Schema, ModelSchema

exclude = model.exclude_in_response

class {model_name}{action}ResponseMainSchema(ModelSchema):
    class Meta:
        model = model
        if not exclude:
            fields = "__all__"
        else:
            exclude = exclude

class {model_name}{action}ResponseDetailsSchema(Schema):
    details: {model_name}{action}ResponseMainSchema

class {model_name}{action}ResponseIdSchema(Schema):
    id: {model_name}{action}ResponseDetailsSchema

class {schema_name}(Schema):
    {model._meta.model_name}: {model_name}{action}ResponseIdSchema
"""
        return run_new_environment(obj_to_return=schema_name, codes=codes, extra_globals={f'model': model})
        
    @classmethod
    def FRemove_response_schema(cls, model: Model):
        model_name = f"{model._meta.app_label}_{model._meta.model_name}"
        schema_name = f'{model_name}FRemoveResponseSchema'
        codes = f"""
from ninja import Schema
from typing import List

files_fields = model.files_fields

class {model_name}FRemoveResponseMainSchema(Schema):
    success_list: List[str]
    failed_list: List[str]

# {model_name}FieldSchema = type(
#     "{model_name}FRemoveResponseFieldSchema",
#     (Schema,),
#     {{string: {model_name}FRemoveResponseMainSchema for string in string_list}}
# )
class {model_name}FRemoveResponseDetailsSchema(Schema):
    details: {model_name}FRemoveResponseMainSchema

class {model_name}FRemoveResponseIdSchema(Schema):
    id: {model_name}FRemoveResponseDetailsSchema

class {schema_name}(Schema):
    {model._meta.model_name}: {model_name}FRemoveResponseIdSchema
"""
        return run_new_environment(schema_name, codes, extra_globals={'model': model})

    @classmethod
    def D_response_schema(cls, model: Model):
        model_name = f"{model._meta.app_label}_{model._meta.model_name}"
        schema_name = f'{model_name}DeleteResponseSchema'
        codes = f"""
from ninja import Schema, ModelSchema

class {model_name}DResponseIdSchema(Schema):
    id: dict

class {schema_name}(Schema):
    {model._meta.model_name}: {model_name}DResponseIdSchema
"""
        return run_new_environment(obj_to_return=schema_name, codes=codes, extra_globals={'model': model}) 
    

async def aggregate_create(modelcontroller, request, request_body:Schema, primary_model_schema_name:str, secondary_model:Model, connector_field_name:str, secondary_model_schema_name:str, secondary_model_pfn:str='', ):
    """
    this function can be used when u have to create multiple instances from two models using a single api assuming one is a primary instance and the others are secondary instances encapsulated in a list, each of which is connected to the primary instance through a ForeignKey field. this function assumes the schema names of primary and secondary models for the request & response schemas are same. this func also assumes your request format is of type json (no file fields).

    NOTE:
    - you need to specify request & responses manually for the primary model and the secondary model. they don't auto-generate while using this function.
    - `modelcontroller`: ModelController instance
    - `connector_field_name`: the field name of the secondary model in str format that connects the primary model through a ForeignKey relation
    - `secondary_model_pfn`: secondary_model's parent field name (used for premium checking, to find `max_add`)
    """

    operation_handler = modelcontroller.operation_handler
    request_body = request_body.dict(exclude_unset=True)
    model = modelcontroller.model_to_control

    if modelcontroller.create_premium_check:
        order_checker = modelcontroller.premium_checker()
        await order_checker.initialize(
            product_type=modelcontroller.product_type, 
            asset_model=modelcontroller.product_asset_model,
            model_to_control=model,
            request=request
        )
        p_f_n = modelcontroller.parent_field_name
        p_id = request_body[primary_model_schema_name][p_f_n] if p_f_n else 0
        premium_passed, msg = await order_checker.create_constraints(parent_field_name=p_f_n, parent_id=p_id, create_count=1, )
        if not premium_passed:
            return Response({"message": msg, "payment status": order_checker.payment_status}, status=401)
        
    primarymodel_instance = await operation_handler(request=request, model=model, request_body=request_body[primary_model_schema_name]).save_files_or_instance(create=True, ninja_response=False)
    if isinstance(primarymodel_instance, Response):
        return primarymodel_instance
    primarymodel_instance = primarymodel_instance[0]

    secondarymodel_instances = []
    secondarymodelitems_list = request_body.get(secondary_model_schema_name) or []
    for each in secondarymodelitems_list:
        if modelcontroller.create_premium_check:
            order_checker = modelcontroller.premium_checker()
            await order_checker.initialize(
                product_type=modelcontroller.product_type, 
                asset_model=modelcontroller.product_asset_model,
                model_to_control=secondary_model,
                request=request
            )
            p_f_n = secondary_model_pfn
            p_id = primarymodel_instance.id or 0
            premium_passed, msg = await order_checker.create_constraints(parent_field_name=p_f_n, parent_id=p_id, create_count=1, )
            if not premium_passed:
                return Response({"message": msg, "payment_status": order_checker.payment_status}, status=401)
        each[connector_field_name] = primarymodel_instance
        secondarymodel_instance = await operation_handler(request=request, model=secondary_model, request_body=each).save_files_or_instance(create=True, ninja_response=False)
        if isinstance(secondarymodel_instance, Response):
            return secondarymodel_instance
        secondarymodel_instances.append(secondarymodel_instance[0])

    return {primary_model_schema_name: primarymodel_instance, secondary_model_schema_name: secondarymodel_instances}
