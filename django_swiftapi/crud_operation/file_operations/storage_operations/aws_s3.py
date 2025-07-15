from django.db.models import Model
from django.conf import settings
from django_swiftapi.crud_operation.file_operations.storage_operations.base import BaseStorage
from django_swiftapi.crud_operation.file_operations.storage_operations.utils.aws_s3 import aws_s3_handler



class aws_s3_storage(BaseStorage):

    """
    NOTE: FILES configurations needed in settings.py to use this storage class:

    PUBLIC_AMAZONS3_BUCKET_NAME = "" # bucket name for public files, ex: 'public-bucket-name'. if you are in production, make sure this bucket is publicly accessible.
    PUBLIC_AMAZONS3_FILE_WRITE_LOCATION = "" # folder name where public files are stored inside that bucket, ex: 'public-bucket-name/public'
    PUBLIC_AMAZONS3_FILE_URL_PREFIX = f"https://{PUBLIC_AMAZONS3_BUCKET_NAME}.s3.amazonaws.com/" # url prefix for public files, ex: 'https://public-bucket-name.s3.amazonaws.com/'
    PRIVATE_AMAZONS3_BUCKET_NAME = "" # bucket name for private files, ex: 'private-bucket-name'. if you are in production, make sure this bucket is not publicly accessible.
    PRIVATE_AMAZONS3_FILE_WRITE_LOCATION = "" # folder name where private files are stored, ex: 'private-bucket-name/private'
    MEDIA_ROOT = PUBLIC_LOCAL_FILE_WRITE_LOCATION
    MEDIA_URL = '/media/'  # this value '/media/' is necessary for serving files during development, according to django's default settings.
    """

    async def dir_maker(self, instance:Model, files_param):
        access = files_param.access
        source_dir = files_param.source_dir
        bucket = files_param.amazons3_bucket_name

        if access == "public":
            bucket = bucket or settings.PUBLIC_AMAZONS3_BUCKET_NAME
            source_dir = source_dir or settings.PUBLIC_AMAZONS3_FILE_WRITE_LOCATION
        elif access == "private":
            bucket = bucket or settings.PRIVATE_AMAZONS3_BUCKET_NAME
            source_dir = source_dir or settings.PRIVATE_AMAZONS3_FILE_WRITE_LOCATION

        field_name = files_param.field_name
        dir = f'{source_dir}/{instance._meta.app_label}/{instance._meta.model_name}/{str(instance.id)}/{field_name}'

        return dir, source_dir, bucket

    async def url_maker(self, abs_path:str, files_param, source_dir:str=""):
        access = files_param.access
        source_dir = files_param.source_dir

        if access=='private':
            return abs_path.split('/')[-1]

        source_dir = source_dir or settings.PUBLIC_AMAZONS3_FILE_WRITE_LOCATION
        url = f'{settings.PUBLIC_AMAZONS3_FILE_URL_PREFIX}/{abs_path}'
        
        return url

    async def _files_writer(self, instance:Model, files_param):
        files_uploaded = files_param.files_uploaded

        success_list = []
        failed_list = []

        dir, source_dir, bucket = await self.dir_maker(instance=instance, files_param=files_param)

        for file in files_uploaded:
            filename = file.name
            abs_path = await self.abs_path_maker(dir=dir, filename=filename)
            try:
                await aws_s3_handler(bucket=bucket, file=file, file_path=abs_path).upload()
                success_list.append(await self.url_maker(source_dir=source_dir, abs_path=abs_path, files_param=files_param))
            except:
                failed_list.append(filename)
        return success_list, failed_list
  
    async def _files_retriever(self, instance:Model, files_param):
        dir, source_dir, bucket = await self.dir_maker(instance=instance, files_param=files_param)
            
        success_list = []
        failed_list = []
        file_links = files_param.file_links

        for file_link in file_links:
            abs_path = await self.abs_path_maker(dir=dir, filelink=file_link)
            try:
                file_stream = await aws_s3_handler(bucket=bucket, file_path=abs_path).get_object_iterator()
                success_list.append({abs_path.split('/')[-1]: file_stream})
            except:
                failed_list.append(file_link)

        return success_list, failed_list
  
    async def _files_remover(self, instance:Model, files_param, remove_dir=False):
        
        dir, source_dir, bucket = await self.dir_maker(instance=instance, files_param=files_param)

        if remove_dir:
            try:
                await aws_s3_handler(bucket=bucket, file_path=dir).remove(remove_dir=remove_dir)
                return "operation processed", None
            except:
                return "error occurred", None
            
        success_list = []
        failed_list = []
        file_links = files_param.file_links

        file_paths = []
        for file_link in file_links:
            file_paths.append(await self.abs_path_maker(dir=dir, filelink=file_link))

        s3_success_list = await aws_s3_handler(bucket=bucket, file_paths=file_paths).remove()

        for file_link in file_links:
            if file_link.split('/')[-1] in s3_success_list:
                success_list.append(file_link)
            else:
                failed_list.append(file_link)

        return success_list, failed_list
