# from __future__ import annotations
import os
import uuid
from django.db.models import Model



class BaseStorage():

    """
    Extend this class to create your own storage class.

    NOTE: Link format example for file writes & removes: 
    # "source_dir/{file_prefix='app_label/model_name/instance_id/field_name'}/filename.extension"
    """

    async def dir_maker(instance:Model, files_param):
        """
        Create and return the directory path for storing files related to the model instance.
        Used internally by the storage class.
        """
        pass

    async def abs_path_maker(self, dir:str, filename:str="", filelink:str=""):
        """
        Create and return the absolute file path for storing files related to the model instance.
        Used internally by the storage class.
        """
        if filelink:
            return f'{dir}/{filelink.split("/")[-1]}'
        name, ext = os.path.splitext(filename)
        new_name_ext = f'{name}-{str(uuid.uuid4())[:6]}{ext}'
        return f'{dir}/{new_name_ext}'

    async def url_maker(self,  abs_path:str, files_param, source_dir:str=""):
        """
        Generate a URL (or file identifier for private) from the absolute file path.
        Used internally by the storage class.
        """
        pass

    async def _files_writer(self, instance:Model, files_param):
        """
        Write uploaded files to the specified filesystem.

        Args:
            instance (Model): Django model instance.
            files_param (Files_Param): Contains uploaded file list, chunk size, access level, etc.

        Returns:
            Two lists:
            - List of successfully written file URLs.
            - List of failed file names.
        """
        pass

    async def _files_remover(self, instance:Model, files_param, remove_dir=False):
        """
        Remove files or entire directory from the specified filesystem.

        Args:
            instance (Model): Django model instance.
            files_param (Files_Param): Contains file_links to remove.
            remove_dir (bool, optional): Whether to remove the whole directory.

        Returns:
            Two lists:
            - List of successfully removed file links.
            - List of failed file links.
        """
        pass

    async def _files_retriever(self, instance:Model, files_param):
        """
        Yields chunks of file data from the specified path for streaming purposes.

        Args:
            instance (Model): Django model instance.
            files_param (Files_Param): Contains file_links to retrieve.

        Yields:
            Two lists:
            - List of dictionaries mapping file names to file streams for successfully retrieved files.
            - List of failed file names.
        """
        pass

