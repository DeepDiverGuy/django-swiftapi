from typing import List
from pydantic import BaseModel, Field
# from asgiref.sync import sync_to_async
from django.db.models import Model
from ninja.files import UploadedFile
from PIL import Image



class Files_Param(BaseModel):
    field_name: str = Field(..., description="name of the ArrayField")
    files_uploaded: List[UploadedFile] = Field(default=[], description="actual files")
    file_size_limit: int = Field(default=5, description="size limit of each file in MegaBytes")
    chunk_size: int = Field(default=3, description="max chunk-size to keep in-memory during writing the file in MegaBytes")
    validate_images: bool = Field(default=False, description="boolean for image validation check")

class file_validator:

    def __init__(self, instance, files_param:Files_Param):
        """
        ::Example Arguments::
        instance = instance,
        files_params = {
            "field_name": "images_links",
            "files_uploaded": files,
            "file_size_limit": 5, # size limit of each file in MegaBytes
            "chunk_size": 3, # (not needed here) max size to keep in-memory during writing the file in MegaBytes
        }
        """
        self.instance = instance
        self.files_param = files_param

    async def arrayfield_size_valid(self):
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

    async def file_sizes_valid(self):
        files_uploaded = self.files_param.files_uploaded
        file_size_limit = self.files_param.file_size_limit # in MegaBytes
        for file in files_uploaded:
            if file.size > file_size_limit*1048576: # 1 MB = 1048576 Bytes
                return False
        return True

    async def images_valid(self):
        files_uploaded = self.files_param.files_uploaded
        for file in files_uploaded:
            try:
                image = Image.open(file)
                image.verify()
            except:
                return False
        return True
    
