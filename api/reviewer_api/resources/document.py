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
from reviewer_api.schemas.document import FOIRequestDeleteRecordsSchema, FOIRequestUpdateRecordsSchema, DocumentDeletedPage, FOIRequestUpdateRecordPersonalAttributesSchema
import json
import requests
import logging

from reviewer_api.services.documentservice import documentservice
from reviewer_api.services.docdeletedpageservice import docdeletedpageservice
from reviewer_api.services.jobrecordservice import jobrecordservice

API = Namespace('Document Services', description='Endpoints for deleting and replacing documents')
TRACER = Tracer.get_instance()
CUSTOM_KEYERROR_MESSAGE = "Key error has occured: "

requestapiurl = getenv("FOI_REQ_MANAGEMENT_API_URL")
requestapitimeout = getenv("FOI_REQ_MANAGEMENT_API_TIMEOUT")
@cors_preflight('POST,OPTIONS')
@API.route('/document/delete')
class DeleteDocuments(Resource):
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
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500

@cors_preflight('POST,OPTIONS')
@API.route('/document/update')
class UpdateDocumentAttributes(Resource):
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
            # print("payload: ", payload)
            payload = FOIRequestUpdateRecordsSchema().load(payload)
            result = documentservice().updatedocumentattributes(payload, AuthHelper.getuserid())
            return {'status': result.success, 'message':result.message,'id':result.identifier} , 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500

@cors_preflight('POST,OPTIONS')
@API.route('/document/update/personal')
class UpdateDocumentPersonalAttributes(Resource):
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
            # print("payload personal: ", payload)
            payload = FOIRequestUpdateRecordPersonalAttributesSchema().load(payload)
            result = documentservice().updatedocumentpersonalattributes(payload, AuthHelper.getuserid())
            return {'status': result.success, 'message':result.message,'id':result.identifier} , 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
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
            # get request status
            jsonobj = response.json()
            balancefeeoverrodforrequest = jobrecordservice().isbalancefeeoverrodforrequest(requestid)
            outstandingbalance=0
            if 'cfrfee' in jsonobj and 'feedata' in jsonobj['cfrfee'] and "balanceDue" in jsonobj['cfrfee']['feedata']:
                outstandingbalancestr= jsonobj['cfrfee']['feedata']["balanceDue"]
                outstandingbalance = float(outstandingbalancestr)
            requestinfo = {
                "bcgovcode": jsonobj["bcgovcode"],
                "requesttype": jsonobj["requestType"],
                "validoipcreviewlayer": documentservice().validate_oipcreviewlayer(jsonobj, requestid),
                "outstandingbalance": outstandingbalance,
                "balancefeeoverrodforrequest": balancefeeoverrodforrequest
            }
            documentdivisionslist,result = documentservice().getdocuments(requestid, requestinfo["bcgovcode"])
            return json.dumps({"requeststatuslabel": jsonobj["requeststatuslabel"], "documents": result, "requestnumber":jsonobj["axisRequestId"], "requestinfo":requestinfo, "documentdivisions":documentdivisionslist}), 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
        except requests.exceptions.HTTPError as err:
            logging.error("Request Management API returned the following message: {0} - {1}".format(err.response.status_code, err.response.text))
            return {'status': False, 'message': err.response.text}, err.response.status_code


@cors_preflight('POST,OPTIONS')
@API.route('/document/ministryrequest/<int:ministryrequestid>/deletedpages')
class DeleteDocumenPage(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post(ministryrequestid):
        try:
            payload = request.get_json()
            payload = DocumentDeletedPage().load(payload)
            result = docdeletedpageservice().newdeletepages(ministryrequestid, payload, AuthHelper.getuserinfo())
            return {'status': result.success, 'message':result.message,'id':result.identifier} , 200
        except ValueError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/document/ministryrequest/<int:ministryrequestid>/deletedpages')
class DeleteDocumenPage(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(ministryrequestid):
        try:
            result = docdeletedpageservice().getdeletedpages(ministryrequestid)
            return json.dumps(result), 200
        except ValueError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
