import os
import shutil
import uuid
from typing import Any, List, Literal
from pydantic import BaseModel, Field
# import aiofiles
from asgiref.sync import sync_to_async
from django.db.models import Model
from django.forms.models import model_to_dict
from django.http import StreamingHttpResponse
from django.conf import settings
from ninja.responses import Response
from ninja.files import UploadedFile
from django_swiftapi.crud_operation.files_validators import file_validator
from django_swiftapi.exceptions import SendErrorResponse
from django_swiftapi.crud_operation.utils.aws_s3_utils import aws_s3_handler

"""
# NOTE: FILES configurations needed in settings.py:

# specifications if you are storing files locally
PUBLIC_LOCAL_FILE_WRITE_LOCATION = "" # folder name where public files are stored, ex: 'site_files/public'. if you are in production, make sure this folder is publicly accessible.
PUBLIC_LOCAL_FILE_URL_PREFIX = "/media" # url prefix for public files, ex: '/media'.
PRIVATE_LOCAL_FILE_WRITE_LOCATION = "" # folder name where private files are stored, ex: 'site_files/private'. if you are in production, make sure this folder is not publicly accessible.

# specifications if you are storing files in amazon s3
# PUBLIC_AMAZONS3_BUCKET_NAME = "" # bucket name for public files, ex: 'public-bucket-name'. if you are in production, make sure this bucket is publicly accessible.
# PUBLIC_AMAZONS3_FILE_WRITE_LOCATION = "" # folder name where public files are stored inside that bucket, ex: 'public-bucket-name/public'
# PUBLIC_AMAZONS3_FILE_URL_PREFIX = f"https://{PUBLIC_AMAZONS3_BUCKET_NAME}.s3.amazonaws.com/" # url prefix for public files, ex: 'https://public-bucket-name.s3.amazonaws.com/'
# PRIVATE_AMAZONS3_BUCKET_NAME = "" # bucket name for private files, ex: 'private-bucket-name'. if you are in production, make sure this bucket is not publicly accessible.
# PRIVATE_AMAZONS3_FILE_WRITE_LOCATION = "" # folder name where private files are stored, ex: 'private-bucket-name/private'

# In addition, you need these below in all cases
MEDIA_ROOT = PUBLIC_LOCAL_FILE_WRITE_LOCATION
MEDIA_URL = '/media/'  # this value '/media/' is necessary for serving files during development

# NOTE: Link format for file writes & removes: 
"source_dir/{file_prefix='app_label/model_name/instance_id/field_name'}/filename.extension"

# NOTE: Follow these steps to develop supports for a new platform (other than local or aws s3):
- edit `Files_Param` class and add `storage` Literal
- edit `dir_maker` func and set `source_dir` (and other variable if applicable) for the specified `storage`, for both public & private
- edit `url_maker` func and set `url` (it will be used as public url) for the specified `storage`
- edit `files_upload_handler` class, write a new func (like _files_writer()) with @classmethod, define your logics and `return success_list, failed_list`
- edit `files_upload_handler.instance_files_writer` and add like this:
    `
    elif storage == "your_storage":
        success_list, failed_list = await files_upload_handler._your_files_writer(instance=instance, files_param=files_param)
    `
- edit `files_remove_handler` class, write a new func (like _files_remover()) with @classmethod, define your logics and `return success_list, failed_list`
- edit `files_remove_handler.instance_files_remover` and add like this:
    `
    elif storage == "your_storage":
        success_list, failed_list = await files_remove_handler._your_files_remover(instance=instance, files_param=files_param)
    `
- edit `files_retrieve_handler` class, write a new func (like _files_retriever()) with @classmethod, define your logics and `return success_list, failed_list`
- edit `files_retrieve_handler.instance_files_retriever` and add like this:
    `
    elif storage == "your_storage":
        success_list, failed_list = await files_retrieve_handler._your_files_retriever(instance=instance, files_param=files_param)
    `
"""


as3_handler = aws_s3_handler

async def ninja_response_with_info(info=None, error_msg=None):
    if info:
        return Response(info, status=200)
    elif error_msg:
        return Response({"error": error_msg}, status=400)

def file_iterator(file_path, chunk_size=1048576):  # 1 MB = 1048576 bytes
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            yield chunk
    # django's StreamingHTTPResponse doesn't yet support asynchronous file-iterator, so we can't use the codes below
    # async with aiofiles.open(file_path, 'rb') as f:
    #     while True:
    #         chunk = await f.read(chunk_size)
    #         if not chunk:
    #             break
    #         yield chunk

class Files_Param(BaseModel):
    access: Literal["public", "private"]
    storage: Literal["local", "amazons3"] = Field(default="local")
    amazons3_bucket_name: str = Field(default=None, description="amazon s3 bucket name. will be used from env if not provided")
    source_dir: str = Field(default=None, description="source directory from where file-prefix directories will start. if you specified 'access' as 'public', then make sure this dir is publicly accessible, else files can't be accessed using the saved links")
    field_name: str = Field(..., description="name of the ArrayField which contains the links")
    files_uploaded: List[UploadedFile] = Field(default=[], description="actual files to write")
    file_links: List[str] = Field(default=[], description="ArrayField that contains links or names of the files to remove")
    file_size_limit: int = Field(default=None, description="size limit of each file in MegaBytes, None means no limit")
    chunk_size: int = Field(default=None, description="max size to keep in-memory during writing each file (in MegaBytes)")
    validate_images: bool = Field(default=False, description="boolean for image validation check")

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

async def dir_maker(instance:Model, files_param:Files_Param):
    access = files_param.access
    storage = files_param.storage
    source_dir = files_param.source_dir
    bucket = files_param.amazons3_bucket_name

    if storage=='local':
        if not source_dir:
            if access == "public":
                source_dir = settings.PUBLIC_LOCAL_FILE_WRITE_LOCATION
            elif access == "private":
                source_dir = settings.PRIVATE_LOCAL_FILE_WRITE_LOCATION

    elif storage=='amazons3':
        if access == "public":
            bucket = bucket or settings.PUBLIC_AMAZONS3_BUCKET_NAME
            source_dir = source_dir or settings.PUBLIC_AMAZONS3_FILE_WRITE_LOCATION
        elif access == "private":
            bucket = bucket or settings.PRIVATE_AMAZONS3_BUCKET_NAME
            source_dir = source_dir or settings.PRIVATE_AMAZONS3_FILE_WRITE_LOCATION

    field_name = files_param.field_name
    dir = f'{source_dir}/{instance._meta.app_label}/{instance._meta.model_name}/{str(instance.id)}/{field_name}'
    return dir, source_dir, bucket

async def abs_path_maker(dir:str, filename:str=None, filelink:str=None):
    if filelink:
        return f'{dir}/{filelink.split("/")[-1]}'
    name, ext = os.path.splitext(filename)
    new_name_ext = f'{name}-{str(uuid.uuid4())[:6]}{ext}'
    return f'{dir}/{new_name_ext}'

async def url_maker(abs_path:str, files_param:Files_Param, source_dir:str=None):
    access = files_param.access
    storage = files_param.storage
    source_dir = files_param.source_dir

    if access=='private':
        return abs_path.split('/')[-1]

    if storage=='local':
        source_dir = source_dir or settings.PUBLIC_LOCAL_FILE_WRITE_LOCATION
        url = abs_path.replace(source_dir, "") if source_dir else abs_path
        url = f'{settings.PUBLIC_LOCAL_FILE_URL_PREFIX}{url}'
    elif storage=='amazons3':
        url = f'{settings.PUBLIC_AMAZONS3_FILE_URL_PREFIX}/{abs_path}'
    
    return url

class files_upload_handler():
    """
    this is a files-upload-handler which assumes that you store the file-links in a django ArrayField. it can validate, write the files & send appropriate ninja-responses.
    """

    def __init__(self, upload_payload:Payload):
        """
        ::Example Usage::
        handler = files_upload_handler(
            Payload(
                configs=[
                    Config(
                        create_instance=True,
                        instance=django-model-instance, 
                        exclude_in_response=[],
                        files_params=[
                            Files_Param(
                                access=""
                                storage="",
                                amazons3_bucket_name="", # don't set to use default from env
                                source_dir="", # don't set to use default from env
                                field_name="", 
                                files_uploaded=[],
                                file_size_limit=20,
                                chunk_size=2.5, # don't set to use default
                                validate_images=True,
                            ),
                        ]
                    ),
                ]
            )
        )
        return await handler.process(ninja_response=True)
        """
        self.configs = upload_payload.configs

    @classmethod
    async def _files_writer(cls, instance:Model, files_param:Files_Param):

        files_uploaded = files_param.files_uploaded
        chunk_size = files_param.chunk_size*1048576 if files_param.chunk_size else None

        success_list = []
        failed_list = []

        dir, source_dir, _ = await dir_maker(instance=instance, files_param=files_param)
        if not os.path.exists(dir):
            os.makedirs(dir)

        for file in files_uploaded:
            filename = file.name
            abs_path = await abs_path_maker(dir=dir, filename=filename)
            try:
                with open(abs_path, 'wb+') as destination:
                    for chunk in file.chunks(chunk_size=chunk_size):
                        destination.write(chunk)
                success_list.append(await url_maker(source_dir=source_dir, abs_path=abs_path, files_param=files_param))
            except:
                failed_list.append(filename)
        return success_list, failed_list
    
    @classmethod
    async def _files_writer_s3(cls, instance:Model, files_param:Files_Param):
        files_uploaded = files_param.files_uploaded

        success_list = []
        failed_list = []

        dir, source_dir, bucket = await dir_maker(instance=instance, files_param=files_param)

        for file in files_uploaded:
            filename = file.name
            abs_path = await abs_path_maker(dir=dir, filename=filename)
            try:
                await as3_handler(bucket=bucket, file=file, file_path=abs_path).upload()
                success_list.append(await url_maker(source_dir=source_dir, abs_path=abs_path, files_param=files_param))
            except:
                failed_list.append(filename)
        return success_list, failed_list
    
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
            if storage == "local":
                success_list, failed_list = await files_upload_handler._files_writer(instance=instance, files_param=files_param)
            elif storage == "amazons3":
                success_list, failed_list = await files_upload_handler._files_writer_s3(instance=instance, files_param=files_param)
            field_value += success_list
            info[instance._meta.model_name][str(instance.id)][field_name] = {"failed_list": failed_list} # "success_list": success_list,
        # print(info[instance._meta.model_name][str(instance.id)]["details"])
        return instance, info
    
    async def validation_checks(self):
        '''
        this is where you write ALL the validation checks.
        '''
        error_message = {}
        for config in self.configs:
            instance = config.instance
            for files_param in config.files_params:
                validator = file_validator(instance=instance, files_param=files_param)
                if not await validator.arrayfield_size_valid():
                    # raise ValueError("maximum allowed number of files exceeded")
                    error_message[f"{files_param.field_name}"] = "maximum allowed number of files exceeded"
                    return error_message
                    
                if files_param.file_size_limit:
                    if not await validator.file_sizes_valid():
                        # raise ValueError("one or more files have exceeded file-size limit")
                        error_message[f"{files_param.field_name}"] = "one or more files have exceeded file-size limit"
                        return error_message
                
                if files_param.validate_images:
                    if not await validator.images_valid():
                        # raise ValueError("one or more images are invalid")
                        error_message[f"{files_param.field_name}"] = "one or more images are invalid"
                        return error_message
                    
    async def process(self, ninja_response=False, request=None):
        error_message = await self.validation_checks()
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
    this is a files-remove-handler which assumes that you store the file-links in a django ArrayField. it can remove the files & send appropriate ninja-responses.
    """

    def __init__(self, payload:Payload):
        """
        ::Example Usage::
        handler = files_remove_handler(
            Payload(
                configs=[
                    Config(
                    delete_instance=True,
                        instance=django-model-instance,
                        files_params=[
                            Files_Param(
                                access="",
                                storage="",
                                amazons3_bucket_name="", # don't set to use default from env
                                source_dir="", # don't set to use default from env
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
    
    @classmethod
    async def _files_remover(cls, instance:Model, files_param:Files_Param, remove_dir=False):
        dir, source_dir, _ = await dir_maker(instance=instance, files_param=files_param)

        if remove_dir:
            if os.path.exists(dir):
                try:
                    shutil.rmtree(dir)
                    return "operation processed", None
                except:
                    return "error occurred", None
            return "directory not found", None
        
        success_list = []
        failed_list = []
        file_links = files_param.file_links

        for file_link in file_links:
            abs_path = await abs_path_maker(dir=dir, filelink=file_link)
            try:
                os.remove(abs_path)
                success_list.append(file_link)
            except FileNotFoundError:
                success_list.append(file_link)
            except:
                failed_list.append(file_link)
        return success_list, failed_list

    @classmethod    
    async def _files_remover_s3(cls, instance:Model, files_param:Files_Param, remove_dir=False):

        dir, source_dir, bucket = await dir_maker(instance=instance, files_param=files_param)

        if remove_dir:
            try:
                await as3_handler(bucket=bucket, file_path=dir).remove(remove_dir=remove_dir)
                return "operation processed", None
            except:
                return "error occurred", None
            
        success_list = []
        failed_list = []
        file_links = files_param.file_links

        file_paths = []
        for file_link in file_links:
            file_paths.append(await abs_path_maker(dir=dir, filelink=file_link))

        s3_success_list = await as3_handler(bucket=bucket, file_paths=file_paths).remove()

        for file_link in file_links:
            if file_link.split('/')[-1] in s3_success_list:
                success_list.append(file_link)
            else:
                failed_list.append(file_link)

        return success_list, failed_list
    
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
            if storage == "local":
                success_list, failed_list = await files_remove_handler._files_remover(instance=instance, files_param=files_param, remove_dir=delete_instance)
            elif storage == "amazons3":
                success_list, failed_list = await files_remove_handler._files_remover_s3(instance=instance, files_param=files_param, remove_dir=delete_instance)
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
    this is a files-retrieve-handler which assumes that you store the file-links in a django ArrayField. It can return file-like iterators which you can use to write. You can also respond a single file directly using django's StreamingHttpResponse.
    """

    def __init__(self, payload:Payload):
        """
        ::Example Usage::
        handler = files_remove_handler(
            Payload(
                configs=[
                    Config(
                    delete_instance=True,
                        instance=django-model-instance,
                        files_params=[
                            Files_Param(
                                access="",
                                storage="",
                                amazons3_bucket_name="", # don't set to use default from env
                                source_dir="", # don't set to use default from env
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

    @classmethod
    async def _files_retriever(cls, instance:Model, files_param:Files_Param): # file_prefix:str

        dir, source_dir, _ = await dir_maker(instance=instance, files_param=files_param)
        
        success_list = []
        failed_list = []
        file_links = files_param.file_links

        for file_link in file_links:
            abs_path = await abs_path_maker(dir=dir, filelink=file_link)
            try:
                if not os.path.exists(abs_path):
                    raise Exception
                file_stream = file_iterator(abs_path)
                success_list.append({abs_path.split('/')[-1]: file_stream})
            except:
                failed_list.append(file_link)
        return success_list, failed_list
    
    @classmethod    
    async def _files_retriever_s3(cls, instance:Model, files_param:Files_Param):

        dir, source_dir, bucket = await dir_maker(instance=instance, files_param=files_param)
            
        success_list = []
        failed_list = []
        file_links = files_param.file_links

        for file_link in file_links:
            abs_path = await abs_path_maker(dir=dir, filelink=file_link)
            try:
                file_stream = await as3_handler(bucket=bucket, file_path=abs_path).get_object_iterator()
                success_list.append({abs_path.split('/')[-1]: file_stream})
            except:
                failed_list.append(file_link)

        return success_list, failed_list
    
    async def instance_files_retriever(self, config:Config):
        instance = config.instance
        self.files[instance._meta.model_name] = {}
        self.files[instance._meta.model_name][str(instance.id)] = {}
        for files_param in config.files_params:
            storage = files_param.storage
            field_name = files_param.field_name
            self.files[instance._meta.model_name][str(instance.id)][field_name] = {}
            if storage == "local":
                success_list, failed_list = await files_retrieve_handler._files_retriever(instance=instance, files_param=files_param)
            elif storage == "amazons3":
                success_list, failed_list = await files_retrieve_handler._files_retriever_s3(instance=instance, files_param=files_param)
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
    
