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

from flask_restx import Namespace, Resource
from flask_cors import cross_origin
from flask import request
from reviewer_api.auth import auth, AuthHelper

from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
from reviewer_api.schemas.documentpageflag import PageflagSchema, BulkDocumentPageflagSchema
import json

from reviewer_api.services.documentpageflagservice import documentpageflagservice


API = Namespace('Document Pageflag Services', description='Endpoints for deleting and replacing documents')
TRACER = Tracer.get_instance()
CUSTOM_KEYERROR_MESSAGE = "Key error has occured: "



@cors_preflight('POST,OPTIONS')
@API.route('/ministryrequest/<requestid>/pageflags')
class SaveDocumentPageflag(Resource):
    """Add document to deleted list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(requestid):
        try:
            payload = BulkDocumentPageflagSchema().load(request.get_json())
            result = documentpageflagservice().bulksavepageflag(requestid, payload, AuthHelper.getuserinfo())
            return {'status': True, 'message':"Page Flag is saved", 'id': requestid, "updatedpageflag": result} , 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
        

# @cors_preflight('GET,OPTIONS')
# @API.route('/ministryrequest/<requestid>/pageflag/<redactionlayer>')
# class GetDocumentPageflag(Resource):
#     """Get document page flag list.
#     """
#     @staticmethod
#     @TRACER.trace()
#     @cross_origin(origins=allowedorigins())
#     #@auth.require
#     #@auth.ismemberofgroups(getrequiredmemberships())
#     def get(requestid, redactionlayer):
#         try:
#             documentids = request.args.getlist('documentids[]')
#             result = documentpageflagservice().getpageflags_by_requestid_docids(requestid, redactionlayer, documentids)
#             return json.dumps(result), 200
#         except KeyError as error:
#             return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
#         except BusinessException as exception:
#             return {'status': exception.status_code, 'message':exception.message}, 500
        

@cors_preflight('POST,OPTIONS')
@API.route('/ministryrequest/<requestid>/pageflag/<redactionlayer>')
class GetDocumentPageflag(Resource):
    """Get document page flag list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(requestid, redactionlayer):
        try:
            payload = request.get_json()
            documentids = payload["documentids"]
            result = documentpageflagservice().getpageflags_by_requestid_docids(requestid, redactionlayer, documentids)
            return json.dumps(result), 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500