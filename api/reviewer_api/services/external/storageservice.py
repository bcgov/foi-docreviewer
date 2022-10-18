import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth
import os
import uuid
import mimetypes
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from reviewer_api.auth import AuthHelper

formsbucket = os.getenv('OSS_S3_FORMS_BUCKET')
accesskey = os.getenv('OSS_S3_FORMS_ACCESS_KEY_ID') 
secretkey = os.getenv('OSS_S3_FORMS_SECRET_ACCESS_KEY')
s3host = os.getenv('OSS_S3_HOST')
s3region = os.getenv('OSS_S3_REGION')
s3service = os.getenv('OSS_S3_SERVICE')
class storageservice:
    """This class is reserved for S3 storage services integration.
    """
    
    def retrieve_s3_presigned(self, filepath, category="attachments", bcgovcode=None):
        formsbucket = self.__getbucket(category, bcgovcode)
        s3client = self.__get_s3client()
        filename, file_extension = os.path.splitext(filepath)    
        response = s3client.generate_presigned_url(
            ClientMethod='get_object',
            Params=   {'Bucket': formsbucket, 'Key': '{0}'.format(filepath),'ResponseContentType': '{0}/{1}'.format('image' if file_extension in ['.png','.jpg','.jpeg','.gif'] else 'application',file_extension.replace('.',''))},
            ExpiresIn=3600,HttpMethod='GET'
        )
        return response

    def __getbucket(self, category, programarea=None):
        docpathmappers = Documents().getdocumentpath()
        defaultbucket = None
        for docpathmapper in docpathmappers:
            if docpathmapper['category'].lower() == "attachments":
                defaultbucket = self.__formatbucketname(docpathmapper['bucket'], programarea)
            if docpathmapper['category'].lower() == category.lower():
                return self.__formatbucketname(docpathmapper['bucket'], programarea)
        return  defaultbucket 

    def __formatbucketname(self, bucket, bcgovcode):
        _bucket = bucket.replace('$environment', self.s3environment)
        if bcgovcode is not None:
            _bucket = _bucket.replace('$bcgovcode', bcgovcode.lower())
        return _bucket        

    def __get_s3client(self):
        ministrygroups = AuthHelper.getministrygroups()
        #recordaccessaccount=getserviceaccountfors3(ministrygroups[0])
        #use recordaccessaccount data for getting accesskey and secret.
        return boto3.client('s3',config=Config(signature_version='s3v4'),
            endpoint_url='https://{0}/'.format(self.s3host),
            aws_access_key_id= self.recordsaccesskey,
            aws_secret_access_key= self.recordssecretkey,
            region_name= self.s3region
        )


    #def getserviceaccountfors3(ministrygroup):
        #To Do: Get service account data from new db with 
        # teamname=ministrygroup.