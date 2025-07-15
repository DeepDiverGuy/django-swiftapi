# from __future__ import annotations
from typing import Any, List, Literal, Dict, Union, Callable, Coroutine
from pydantic import BaseModel, Field
from asgiref.sync import sync_to_async
# from django.db.models import Model
from django.forms.models import model_to_dict
from django.http import StreamingHttpResponse
# from django.conf import settings
from ninja.responses import Response
from ninja.files import UploadedFile
from django_swiftapi.crud_operation.file_operations.files_validators import file_validator
# from django_swiftapi.crud_operation.file_operations.storage_operations.base import BaseStorage
# from django_swiftapi.crud_operation.file_operations.storage_operations.utils.aws_s3 import aws_s3_handler
from django_swiftapi.exceptions import SendErrorResponse



async def ninja_response_with_info(info=None, error_msg=None):
    if info:
        return Response(info, status=200)
    elif error_msg:
        return Response({"error": error_msg}, status=400)

class Files_Param(BaseModel):
    access: Literal["public", "private"]
    storage: Any  # Type[BaseStorage]
    # amazons3_bucket_name: str = Field(default=None, description="amazon s3 bucket name. override this to not use the default from settings.py")
    source_dir: str = Field(default=None, description="source directory from where file-prefix directories will start. if you specified 'access' as 'public', then make sure this dir is publicly accessible, else files can't be accessed using the saved links")
    field_name: str = Field(..., description="name of the ArrayField which contains the file-links")
    files_uploaded: List[UploadedFile] = Field(default=[], description="actual files to write")
    file_links: List[str] = Field(default=[], description="links or names of the files to remove")
    chunk_size: int = Field(default=None, description="max size to keep in-memory during writing each file (in MegaBytes)")
    validator_funcs: Dict[Union[Callable[..., Any], Callable[..., Coroutine[Any, Any, Any]]], Dict[str, Any]] = Field(default={}, description="Dictionary of sync/async validator functions mapped to their keyword arguments.")

class Config(BaseModel):
    create_instance: bool = False
    delete_instance: bool = False
    instance: Any
    exclude_in_response: list = Field(default=[], description="this specifies the fields to exclude in response")
    files_params: List[Files_Param] = Field(default=[])
    m2m_fields: list[tuple[str, list]] = Field(default=[])

    # class Config:
    #     arbitrary_types_allowed = True

class Payload(BaseModel):
    configs: List[Config]

class files_upload_handler():
    """
    Handles file uploads for Django models that use `ArrayField` to store file links.

    Supports validation, writing files, and returning appropriate Ninja responses.
    """


    def __init__(self, upload_payload:Payload):
        """
        Example usage:
            handler = files_upload_handler(
                Payload(
                    configs=[
                        Config(
                            create_instance=True,
                            instance=<django-model-instance>, 
                            exclude_in_response=[],
                            files_params=[
                                Files_Param(
                                    access="",
                                    storage=<storage_class>,
                                    source_dir="", # default is recommended
                                    field_name="", 
                                    files_uploaded=[],
                                    chunk_size=2.5, # default is 2.5MB
                                    validator_funcs={
                                        django_swiftapi.crud_operation.files_validators.file_sizes_valid: {"limit": 20},
                                        django_swiftapi.crud_operation.files_validators.images_valid: {},
                                    }
                                ),
                            ]
                        ),
                    ]
                )
            )
            return await handler.process(ninja_response=True)
        """
        self.configs = upload_payload.configs
    
    async def instance_files_writer(self, info:dict, config:Config, request=None):
        instance = config.instance
        if config.create_instance:
            await instance.asave(request=request)
        info[instance._meta.model_name] = {}
        info[instance._meta.model_name][str(instance.id)] = {}
        info[instance._meta.model_name][str(instance.id)]["details"] = await sync_to_async(model_to_dict)(instance, exclude=config.exclude_in_response)
        for files_param in config.files_params:
            storage = files_param.storage
            field_name = files_param.field_name
            field_value = getattr(instance, field_name)
            success_list, failed_list = await storage()._files_writer(instance=instance, files_param=files_param)
            field_value += success_list
            info[instance._meta.model_name][str(instance.id)][field_name] = {"failed_list": failed_list} # "success_list": success_list,
        # print(info[instance._meta.model_name][str(instance.id)]["details"])
        return instance, info
    
    async def _validation_checks(self):
        error_message = {}
        for config in self.configs:
            instance = config.instance
            for files_param in config.files_params:
                validator = file_validator(instance=instance, files_param=files_param)
                if not await validator._arrayfield_size_valid():
                    # raise ValueError("maximum allowed number of files exceeded")
                    error_message[f"{files_param.field_name}"] = "maximum allowed number of files exceeded"
                    return error_message

                if files_param.validator_funcs:
                    return await validator._validate_funcs()
                    
    async def process(self, ninja_response=False, request=None):
        error_message = await self._validation_checks()
        if error_message:
            return await ninja_response_with_info(error_msg=error_message) if ninja_response else error_message
        info = {}
        instances = []
        try:
            for config in self.configs:
                instance, info = await self.instance_files_writer(info=info, config=config, request=request)
                for field_name, field_value in config.m2m_fields:
                    await getattr(instance, field_name).aset(field_value)
                if config.create_instance and not config.files_params:
                    instances.append(instance)
                    continue
                await instance.asave(request=request)
                if not 'created' in config.exclude_in_response:
                    info[instance._meta.model_name][str(instance.id)]["details"]['created'] = instance.created
                if not 'updated' in config.exclude_in_response:
                    info[instance._meta.model_name][str(instance.id)]["details"]['updated'] = instance.updated
                instances.append(instance)
        except SendErrorResponse as r:
            return await ninja_response_with_info(error_msg=r.error_message)
        if ninja_response:
            return await ninja_response_with_info(info=info)
        return instances
        
class files_remove_handler():
    """
    Handles file removals for Django models that use `ArrayField` to store file links.

    Supports removing files and returning appropriate Ninja responses.
    """

    def __init__(self, payload:Payload):
        """
        Example usage:
            handler = files_remove_handler(
                Payload(
                    configs=[
                        Config(
                        delete_instance=True,
                            instance=<django-model-instance>,
                            files_params=[
                                Files_Param(
                                    access="",
                                    storage=<storage_class>,
                                    source_dir="", # default is recommended
                                    field_name="",
                                    file_links=[]
                                ),
                            ]
                        ),
                    ]
                )
            )
            return await handler.process(ninja_response=True)
        """
        self.configs = payload.configs
    
    async def instance_files_remover(self, info:dict, config:Config):
        instance = config.instance
        info[instance._meta.model_name] = {}
        info[instance._meta.model_name][str(instance.id)] = {}
        for files_param in config.files_params:
            storage = files_param.storage
            delete_instance = config.delete_instance
            field_name = files_param.field_name
            field_value = getattr(instance, field_name)
            info[instance._meta.model_name][str(instance.id)][field_name] = {}
            success_list, failed_list = await storage()._files_remover(instance=instance, files_param=files_param, remove_dir=delete_instance)
            if delete_instance:
                info[instance._meta.model_name][str(instance.id)][field_name] = success_list
                continue
            for deleted_image in success_list:
                try:
                    field_value.remove(deleted_image)
                except:
                    pass
            info[instance._meta.model_name][str(instance.id)][field_name] = {"success_list": success_list, "failed_list": failed_list}
        return instance, info

    async def process(self, ninja_response=False, request=None):
        info = {}
        instances = []
        try:
            for config in self.configs:
                instance, info = await self.instance_files_remover(info=info, config=config)
                if config.delete_instance:
                    await instance.adelete()
                    continue
                await instance.asave(request=request)
                instances.append(instance)
        except SendErrorResponse as r:
            return await ninja_response_with_info(error_msg=r.error_message)
        if ninja_response:
            return await ninja_response_with_info(info=info)
        return instances

class files_retrieve_handler():
    """
    Handles file retrievals for Django models that use `ArrayField` to store file links.

    Supports returning file-like iterators or a single file using Django's `StreamingHttpResponse`.
    """

    def __init__(self, payload:Payload):
        """
        Example usage:
            handler = files_remove_handler(
                Payload(
                    configs=[
                        Config(
                        delete_instance=True,
                            instance=<django-model-instance>,
                            files_params=[
                                Files_Param(
                                    access="",
                                    storage=<storage_class>,
                                    source_dir="", # default is recommended
                                    field_name="",
                                    file_links=[]
                                ),
                            ]
                        ),
                    ]
                )
            )
            return await handler.process(ninja_response=True)
        """
        self.configs = payload.configs
        self.files = {}
    
    async def instance_files_retriever(self, config:Config):
        instance = config.instance
        self.files[instance._meta.model_name] = {}
        self.files[instance._meta.model_name][str(instance.id)] = {}
        for files_param in config.files_params:
            storage = files_param.storage
            field_name = files_param.field_name
            self.files[instance._meta.model_name][str(instance.id)][field_name] = {}
            success_list, failed_list = await storage()._files_retriever(instance=instance, files_param=files_param)
            self.files[instance._meta.model_name][str(instance.id)][field_name] = {"success_list": success_list, "failed_list": failed_list}

    async def process(self, django_streaming_response=False):

        for config in self.configs:
            await self.instance_files_retriever(config=config)

        files = self.files
        if django_streaming_response:
            current_level = files
            while isinstance(current_level, dict):
                current_level = next(iter(current_level.values()))
            
            if len(current_level)==1:
                file_dict = current_level[0]
                for key, value in file_dict.items():
                    response = StreamingHttpResponse(value, content_type='application/octet-stream')
                    response['Content-Disposition'] = f'attachment; filename="{key}"'
                return response
            else:
                return await ninja_response_with_info(error_msg="error occurred. Hint: ensure you sent the correct filename/url and requested only one file")

        return files
    
