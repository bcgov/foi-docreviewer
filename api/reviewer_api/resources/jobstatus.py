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
from reviewer_api.auth import auth, AuthHelper

from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
import json
from flask import request
from reviewer_api.services.documentservice import documentservice
from reviewer_api.services.jobrecordservice import jobrecordservice

API = Namespace('Job Status', description='Endpoints for getting and posting deduplication and file conversion job status of documents')
TRACER = Tracer.get_instance()

@cors_preflight('GET,OPTIONS')
@API.route('/dedupestatus/<requestid>')
class GetDedupeStatus(Resource):
    """Get document list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(requestid):
        try:
            result = documentservice().getdedupestatus(requestid)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500

@cors_preflight('POST,OPTIONS')
@API.route('/jobstatus')
class GetDedupeStatus(Resource):
    """Insert entries into job record table.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post():
        try:
            requestjson = request.get_json()
            result = jobrecordservice().recordjobstatus(requestjson, AuthHelper.getuserid())
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
        
@cors_preflight('POST,OPTIONS')
@API.route('/pdfstitchjobstatus')
class AddPDFStitchJobStatus(Resource):
    """Insert entries into job record table.
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post():
        try:
            requestjson = request.get_json()
            result = jobrecordservice().insertpdfstitchjobstatus(requestjson, AuthHelper.getuserid())
            respcode = 200 if result.success == True else 500
            return {'status': result.success, 'message':result.message,'id':result.identifier}, respcode
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/pdfstitchjobstatus/<requestid>/<category>')
class GetPDFStitchJobStatus(Resource):
    """Get document list.
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(requestid, category):
        try:
            result = jobrecordservice().getpdfstitchjobstatus(requestid, category)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
        
@cors_preflight('GET,OPTIONS')
@API.route('/recordschanged/<requestid>/<category>')
class GetPDFStitchJobStatus(Resource):
    """Get document list.
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(requestid, category):
        try:
            result = jobrecordservice().getrecordschanged(requestid, category)
            print("getrecordschanged = ", result)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            print("error = ", exception.message)
            return {'status': exception.status_code, 'message':exception.message}, 500
        except Exception as ex:
            print("ex = ", ex)
        
    