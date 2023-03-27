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
from reviewer_api.schemas.documentpageflag import DocumentPageflagSchema
import json

from reviewer_api.services.documentpageflagservice import documentpageflagservice

API = Namespace('Document Services', description='Endpoints for deleting and replacing documents')
TRACER = Tracer.get_instance()

@cors_preflight('POST,OPTIONS')
@API.route('/ministryrequest/<requestid>/document/<documentid>/version/<documentversion>/pageflag')
class SaveDocumentPageflag(Resource):
    """Add document to deleted list.
    """
    @staticmethod
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post(requestid, documentid, documentversion):
        try:
            payload = request.get_json()
            payload = DocumentPageflagSchema().load(payload)
            result = documentpageflagservice().savepageflag(requestid, documentid, documentversion, payload, AuthHelper.getuserinfo())
            return {'status': result.success, 'message':result.message,'id':result.identifier} , 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500

@cors_preflight('GET,OPTIONS')
@API.route('/ministryrequest/<requestid>/document/<documentid>/version/<documentversion>/pageflag')
class GetDocumentPageflag(Resource):
    """Get document page flag list.
    """
    @staticmethod
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(requestid, documentid, documentversion):
        try:
            result = documentpageflagservice().getdocumentpageflags(requestid, documentid, documentversion)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/ministryrequest/<requestid>/pageflag')
class GetDocumentPageflag(Resource):
    """Get document page flag list.
    """
    @staticmethod
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(requestid):
        try:
            result = documentpageflagservice().getpageflags(requestid)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500