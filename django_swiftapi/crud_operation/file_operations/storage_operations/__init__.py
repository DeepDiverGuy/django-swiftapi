from .base import BaseStorage
from .local import local_storage
from .aws_s3 import aws_s3_storage



__all__ = ["BaseStorage", "local_storage", "aws_s3_storage"]

