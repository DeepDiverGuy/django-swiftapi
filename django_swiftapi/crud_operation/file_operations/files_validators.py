import inspect
from typing import List, Callable, Coroutine, Union, Dict, Any
from pydantic import BaseModel, Field
from django.db.models import Model
from ninja.files import UploadedFile
from PIL import Image



class Files_Param(BaseModel):
    """
    Parameters for handling file uploads and validations.

    Attributes:
        field_name (str): Name of the ArrayField.
        files_uploaded (List[UploadedFile]): List of uploaded files.
        chunk_size (int): Max chunk size in MB for in-memory file writing.
        validator_funcs (Dict[Callable, Dict[str, Any]]): 
            Dictionary mapping sync/async validator functions to their kwargs.
    """
    field_name: str = Field(..., description="name of the ArrayField")
    files_uploaded: List[UploadedFile] = Field(default=[], description="actual files")
    chunk_size: int = Field(default=3, description="max chunk-size to keep in-memory during writing the file in MegaBytes")
    validator_funcs: Dict[Union[Callable[..., Any], Callable[..., Coroutine[Any, Any, Any]]], Dict[str, Any]] = Field(
        default={}, 
        description="Dictionary of sync/async validator functions mapped to their keyword arguments."
    )

class file_validator:

    """
    Initialize file_validator with model instance and file parameters.

    Args:
        instance: Model instance related to the files.
        files_param (Files_Param): File upload and validation parameters.

    Example usage:
        instance = instance,
        files_params = {
            "field_name": "images_links",
            "files_uploaded": <actual_files_uploaded>,
            "chunk_size": 3,  # max chunk size in MB for file writing
            "validator_funcs": {
                <function>: {"<argument_name>": <argument_value>},
            }
        }
    """

    def __init__(self, instance, files_param: Files_Param):
        self.instance = instance
        self.files_param = files_param
    
    async def _arrayfield_size_valid(self):
        field_name = self.files_param.field_name
        field_value = getattr(self.instance, field_name) if isinstance(self.instance, Model) else []
        number_of_files_uploaded = len(self.files_param.files_uploaded)
        # the code below can be used if we don't wanna send the field-name as str as an argument, rather use the value of that field
        # if not field_name:
        #     for field in self.instance._meta.fields:
        #         if await sync_to_async(getattr)(self.instance, field.name) == field_value:
        #             field_name = field.name
        #             break
        max_size = self.instance._meta.get_field(field_name).size
        if len(field_value) + number_of_files_uploaded > max_size:
            return False
        return True

    async def _validate_funcs(self):
        for func, kwargs in self.files_param.validator_funcs.items():
            error_message = await func(self, **kwargs) if inspect.iscoroutinefunction(func) else func(self, **kwargs)
            if error_message:
                return error_message
        # return True


async def validate_file_sizes(self, limit:int):
    """
    Validates that uploaded files do not exceed the given size limit.

    Args:
        self: The calling object with `self.files_param.files_uploaded`.
        limit (int): Max allowed size in megabytes.

    Returns:
        str | None: Error message if validation fails; None if valid.

    Example usage:
        validator_funcs = {
            django_swiftapi.crud_operation.file_operations.files_validators.validate_file_sizes: {"limit": 5},
        }
    """
    files_uploaded = self.files_param.files_uploaded
    # limit = self.files_param.limit # in MegaBytes
    for file in files_uploaded:
        if file.size > limit*1048576: # 1 MB = 1048576 Bytes
            return "one or more files have exceeded file-size limit"
    # return True

async def validate_images(self):
    """
    Validates that uploaded files are valid image files.
    Attempts to open and verify each uploaded file using Pillow.
    Returns an error message if any file is not a valid image.

    Args:
        self: The calling object with `self.files_param.files_uploaded`.

    Returns:
        str | None: Error message if validation fails; None if all files are valid images.

    Example usage:
        validator_funcs = {
            django_swiftapi.crud_operation.file_operations.files_validators.validate_images: {},
        }
    """
    files_uploaded = self.files_param.files_uploaded
    for file in files_uploaded:
        try:
            image = Image.open(file)
            image.verify()
        except:
            return "one or more images are invalid"
    # return True


