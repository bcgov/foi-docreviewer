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
from os import getenv

from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
from reviewer_api.schemas.document import FOIRequestDeleteRecordsSchema
import json
import requests
import logging

from reviewer_api.services.documentservice import documentservice

API = Namespace('Document Services', description='Endpoints for deleting and replacing documents')
TRACER = Tracer.get_instance()

requestapiurl = getenv("FOI_REQ_MANAGEMENT_API_URL")
requestapitimeout = getenv("FOI_REQ_MANAGEMENT_API_TIMEOUT")
@cors_preflight('POST,OPTIONS')
@API.route('/document/delete')
class GetDedupeStatus(Resource):
    """Add document to deleted list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post():
        try:
            payload = request.get_json()
            payload = FOIRequestDeleteRecordsSchema().load(payload)
            result = documentservice().deletedocument(payload, AuthHelper.getuserid())
            return {'status': result.success, 'message':result.message,'id':result.identifier} , 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500

@cors_preflight('GET,OPTIONS')
@API.route('/document/<requestid>')
class GetDocuments(Resource):
    """Get document list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get(requestid):
        try:
            response = requests.request(
                method='GET',
                url= requestapiurl + "/api/foirequests/ministryrequestid/" + requestid + "/" + AuthHelper.getusertype(),
                headers={'Authorization': AuthHelper.getauthtoken(), 'Content-Type': 'application/json'},
                timeout=float(requestapitimeout)
            )
            response.raise_for_status()
            result = documentservice().getdocuments(requestid)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
        except requests.exceptions.HTTPError as err:
            logging.error("Request Management API returned the following message: {0} - {1}".format(err.response.status_code, err.response.text))
            return {'status': False, 'message': err.response.text}, err.response.status_code
