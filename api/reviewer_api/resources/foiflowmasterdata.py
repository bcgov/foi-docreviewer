# Copyright © 2021 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""API endpoints for managing a FOI Requests resource."""

from logging import Logger
from flask import request, current_app
from flask_restx import Namespace, Resource
from flask_cors import cross_origin
from reviewer_api.auth import auth, AuthHelper


# from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
import json
# import requests
# from reviewer_api.schemas.foirequestsformslist import  FOIRequestsFormsList
from aws_requests_auth.aws_auth import AWSRequestsAuth
import os
# from reviewer_api.utils.cache import cache_filter, response_filter

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from reviewer_api.services.radactionservice import redactionservice

API = Namespace('FOI Flow Master Data', description='Endpoints for FOI Flow master data')
# TRACER = Tracer.get_instance()

# @cors_preflight('GET,OPTIONS')
# @API.route('/foiflow/oss/authheader')
# class FOIFlowDocumentStorage(Resource):
#     """Retrieves authentication properties for document storage.
#     """
#     @staticmethod
#     # @TRACER.trace()
#     @cross_origin(origins=allowedorigins())       
#     @auth.require
#     @auth.ismemberofgroups(getrequiredmemberships())
#     def post():
#         try:

#             formsbucket = os.getenv('OSS_S3_FORMS_BUCKET')
#             accesskey = os.getenv('OSS_S3_FORMS_ACCESS_KEY_ID') 
#             secretkey = os.getenv('OSS_S3_FORMS_SECRET_ACCESS_KEY')
#             s3host = os.getenv('OSS_S3_HOST')
#             s3region = os.getenv('OSS_S3_REGION')
#             s3service = os.getenv('OSS_S3_SERVICE')

#             if(accesskey is None or secretkey is None or s3host is None or formsbucket is None):
#                 return {'status': "Configuration Issue", 'message':"accesskey is None or secretkey is None or S3 host is None or formsbucket is None"}, 500

#             requestfilejson = request.get_json()

#             for file in requestfilejson:                
#                 foirequestform = FOIRequestsFormsList().load(file)                
#                 ministrycode = foirequestform.get('ministrycode')
#                 requestnumber = foirequestform.get('requestnumber')
#                 filestatustransition = foirequestform.get('filestatustransition')
#                 filename = foirequestform.get('filename')
#                 s3sourceuri = foirequestform.get('s3sourceuri')
#                 filenamesplittext = os.path.splitext(filename)
#                 uniquefilename = '{0}{1}'.format(uuid.uuid4(),filenamesplittext[1])                
#                 auth = AWSRequestsAuth(aws_access_key=accesskey,
#                         aws_secret_access_key=secretkey,
#                         aws_host=s3host,
#                         aws_region=s3region,
#                         aws_service=s3service) 

#                 s3uri = s3sourceuri if s3sourceuri is not None else 'https://{0}/{1}/{2}/{3}/{4}/{5}'.format(s3host,formsbucket,ministrycode,requestnumber,filestatustransition,uniquefilename)        
                
#                 response = requests.put(s3uri,data=None,auth=auth) if s3sourceuri is None  else requests.get(s3uri,auth=auth)


#                 file['filepath']=s3uri
#                 file['authheader']=response.request.headers['Authorization'] 
#                 file['amzdate']=response.request.headers['x-amz-date']
#                 file['uniquefilename']=uniquefilename if s3sourceuri is None else ''
#                 file['filestatustransition']=filestatustransition  if s3sourceuri is None else ''
                
                
#             return json.dumps(requestfilejson) , 200
#         except BusinessException as exception:            
#             return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/foiflow/oss/presigned/<documentid>')
class FOIFlowS3Presigned(Resource):

    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    # @auth.documentbelongstosameministry
    def get(documentid):
        try :
            document = redactionservice().getdocument(documentid)
            documentmapper = redactionservice().getdocumentmapper(document["attributes"]["documentpathid"])
            attribute = json.loads(documentmapper["attributes"])

            current_app.logger.debug("Inside Presigned api!!")
            formsbucket = documentmapper["bucket"]
            accesskey = attribute["s3accesskey"]
            secretkey = attribute["s3secretkey"]
            s3host = "citz-foi-prod.objectstore.gov.bc.ca"
            s3region = "us-east-1"
            filepath = document["filepath"]

            s3client = boto3.client('s3',config=Config(signature_version='s3v4'),
                endpoint_url='https://{0}/'.format(s3host),
                aws_access_key_id= accesskey,
                aws_secret_access_key= secretkey,region_name= s3region
                )

            filename, file_extension = os.path.splitext(filepath)
            response = s3client.generate_presigned_url(
                ClientMethod='get_object',
                Params=   {'Bucket': formsbucket, 'Key': '{0}'.format(filepath),'ResponseContentType': '{0}/{1}'.format('image' if file_extension in ['.png','.jpg','.jpeg','.gif'] else 'application',file_extension.replace('.',''))},
                ExpiresIn=3600,HttpMethod='GET'
                )

            return json.dumps(response),200
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500 
          