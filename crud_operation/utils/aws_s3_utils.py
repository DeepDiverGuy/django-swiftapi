from asgiref.sync import sync_to_async
import boto3


s3 = boto3.client('s3')

class aws_s3_handler():
    def __init__(self, bucket:str=None, file=None, file_path:str=None, file_paths:list=[]):
        self.Filename = file
        self.Bucket = bucket
        self.Key = file_path
        self.Keys = file_paths

    async def upload(self):
        self.Filename.file.seek(0)
        await sync_to_async(s3.upload_fileobj)(self.Filename.file, self.Bucket, self.Key)  # ExtraArgs={'ContentType': self.Filename.content_type}

    async def remove(self, remove_dir=False):
        bucket = self.Bucket

        if remove_dir:
            objects_to_delete = s3.list_objects_v2(Bucket=bucket, Prefix=self.Key)
            objects = [{'Key': obj['Key']} for obj in objects_to_delete.get('Contents')]
        else:
            objects = [{'Key': key} for key in self.Keys]

        s3_success_list = []
        # s3_failed_list = []

        if objects:
            response = await sync_to_async(s3.delete_objects)(
                Bucket=bucket,
                Delete={
                    'Objects': objects
                },
            )
            deleted = response.get('Deleted')
            # errors = response.get('Errors')
            if not remove_dir:
                if deleted:
                    for i in deleted:
                        s3_success_list.append(i.get('Key').split('/')[-1])
                # if errors:
                #     for j in errors:
                #         s3_failed_list.append(j.get('Key'))

        return s3_success_list  # , s3_failed_list
    
    async def get_object_iterator(self):
        response = s3.get_object(Bucket=self.Bucket, Key=self.Key)
        return response['Body'].iter_chunks()
    
    async def generate_temp_link(self, expiration:float=6):
        """
        provide `expiration` in hours. default is 6 hours.
        """
        return s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.Bucket,
                    'Key': self.Key
                },
                ExpiresIn=expiration*3600
            )
