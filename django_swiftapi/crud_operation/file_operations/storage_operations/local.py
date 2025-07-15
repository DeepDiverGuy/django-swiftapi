import os
import shutil
from django.db.models import Model
from django.conf import settings
from django_swiftapi.crud_operation.file_operations.storage_operations.base import BaseStorage



class local_storage(BaseStorage):

    """
    NOTE: FILES configurations needed in settings.py to use this storage class:
    PUBLIC_LOCAL_FILE_WRITE_LOCATION = "" # folder name where public files are stored, ex: 'site_files/public'. if you are in production, make sure this folder is publicly accessible.
    PUBLIC_LOCAL_FILE_URL_PREFIX = "" # url prefix for public files, ex: '/media'.
    PRIVATE_LOCAL_FILE_WRITE_LOCATION = "" # folder name where private files are stored, ex: 'site_files/private'. if you are in production, make sure this folder is not publicly accessible.
    MEDIA_ROOT = PUBLIC_LOCAL_FILE_WRITE_LOCATION
    MEDIA_URL = '/media/'  # this value '/media/' is necessary for serving files during development, according to django's default settings.
    """

    async def dir_maker(self, instance:Model, files_param):
        access = files_param.access
        source_dir = files_param.source_dir

        if not source_dir:
            if access == "public":
                source_dir = settings.PUBLIC_LOCAL_FILE_WRITE_LOCATION
            elif access == "private":
                source_dir = settings.PRIVATE_LOCAL_FILE_WRITE_LOCATION

        field_name = files_param.field_name
        dir = f'{source_dir}/{instance._meta.app_label}/{instance._meta.model_name}/{str(instance.id)}/{field_name}'

        return dir, source_dir

    async def url_maker(self, abs_path:str, files_param, source_dir:str=""):
        access = files_param.access
        source_dir = files_param.source_dir

        if access=='private':
            return abs_path.split('/')[-1]

        source_dir = source_dir or settings.PUBLIC_LOCAL_FILE_WRITE_LOCATION
        url = abs_path.replace(source_dir, "") if source_dir else abs_path
        url = f'{settings.PUBLIC_LOCAL_FILE_URL_PREFIX}{url}'
        
        return url

    async def _files_writer(self, instance:Model, files_param):

        files_uploaded = files_param.files_uploaded
        chunk_size = files_param.chunk_size*1048576 if files_param.chunk_size else None

        success_list = []
        failed_list = []

        dir, source_dir = await self.dir_maker(instance=instance, files_param=files_param)
        if not os.path.exists(dir):
            os.makedirs(dir)

        for file in files_uploaded:
            filename = file.name
            abs_path = await self.abs_path_maker(dir=dir, filename=filename)
            try:
                with open(abs_path, 'wb+') as destination:
                    for chunk in file.chunks(chunk_size=chunk_size):
                        destination.write(chunk)
                success_list.append(await self.url_maker(source_dir=source_dir, abs_path=abs_path, files_param=files_param))
            except:
                failed_list.append(filename)
        return success_list, failed_list
    
    async def _files_remover(self, instance:Model, files_param, remove_dir=False):
        dir, source_dir = await self.dir_maker(instance=instance, files_param=files_param)

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
            abs_path = await self.abs_path_maker(dir=dir, filelink=file_link)
            try:
                os.remove(abs_path)
                success_list.append(file_link)
            except FileNotFoundError:
                success_list.append(file_link)
            except:
                failed_list.append(file_link)
        return success_list, failed_list

    def file_iterator(self,file_path, chunk_size=1048576):  # 1 MB = 1048576 bytes
        """
        # django's StreamingHTTPResponse doesn't yet support asynchronous file-iterator, so we can't use async iterator like this:
        # async with aiofiles.open(file_path, 'rb') as f:
        #     while True:
        #         chunk = await f.read(chunk_size)
        #         if not chunk:
        #             break
        #         yield chunk
        """
        with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    yield chunk

    async def _files_retriever(self, instance:Model, files_param): # file_prefix:str

        dir, source_dir = await self.dir_maker(instance=instance, files_param=files_param)
        
        success_list = []
        failed_list = []
        file_links = files_param.file_links

        for file_link in file_links:
            abs_path = await self.abs_path_maker(dir=dir, filelink=file_link)
            try:
                if not os.path.exists(abs_path):
                    raise Exception
                file_stream = self.file_iterator(abs_path)
                success_list.append({abs_path.split('/')[-1]: file_stream})
            except:
                failed_list.append(file_link)
        return success_list, failed_list

