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
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
import json
from aws_requests_auth.aws_auth import AWSRequestsAuth
import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from reviewer_api.services.radactionservice import redactionservice
from reviewer_api.services.documentservice import documentservice

API = Namespace('FOI Flow Master Data', description='Endpoints for FOI Flow master data')

@cors_preflight('GET,OPTIONS')
@API.route('/foiflow/oss/presigned/<documentid>')
class FOIFlowS3Presigned(Resource):

    @staticmethod
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(documentid):
        try :
            document = documentservice().getdocument(documentid)
            documentmapper = redactionservice().getdocumentmapper(document["filepath"].split('/')[3])
            attribute = json.loads(documentmapper["attributes"])

            current_app.logger.debug("Inside Presigned api!!")
            formsbucket = documentmapper["bucket"]
            accesskey = attribute["s3accesskey"]
            secretkey = attribute["s3secretkey"]
            s3host = "citz-foi-prod.objectstore.gov.bc.ca"
            s3region = "us-east-1"
            filepath = '/'.join(document["filepath"].split('/')[4:])
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
          