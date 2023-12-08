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
from flask import request, current_app, jsonify
from flask_restx import Namespace, Resource
from flask_cors import cross_origin
from reviewer_api.auth import auth, AuthHelper

from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import (
    cors_preflight,
    allowedorigins,
    getrequiredmemberships,
)
from reviewer_api.exceptions import BusinessException
import json
import os
from reviewer_api.services.radactionservice import redactionservice

from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.schemas.annotationrequest import (
    AnnotationRequest,
    BulkAnnotationRequest,
    SectionRequestSchema,
    SectionSchema,
)
from reviewer_api.schemas.redline import RedlineSchema
from reviewer_api.schemas.finalpackage import FinalPackageSchema

API = Namespace(
    "Document and annotations",
    description="Endpoints for document and annotation operations",
)
TRACER = Tracer.get_instance()
CUSTOM_KEYERROR_MESSAGE = "Key error has occured: "


@cors_preflight("GET,OPTIONS")
@API.route("/annotation/<int:ministryrequestid>")
@API.route("/annotation/<int:ministryrequestid>/<string:redactionlayer>")
class Annotations(Resource):
    """Retrieves annotations for a document"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get(ministryrequestid, redactionlayer="redline"):
        try:
            isvalid, _redactionlayer = redactionservice().validateredactionlayer(
                redactionlayer, ministryrequestid
            )
            if isvalid == True:
                result = redactionservice().getannotationsbyrequest(
                    ministryrequestid, _redactionlayer
                )
                return json.dumps(result), 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


@cors_preflight("GET,OPTIONS")
@API.route(
    "/annotation/<int:ministryrequestid>/<string:redactionlayer>/<int:page>/<int:size>"
)
class AnnotationPagination(Resource):
    """Retrives the foi request based on the queue type."""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @cors_preflight("GET,OPTIONS")
    @auth.ismemberofgroups(getrequiredmemberships())
    def get(ministryrequestid, redactionlayer="redline", page=1, size=1000):
        try:
            isvalid, _redactionlayer = redactionservice().validateredactionlayer(
                redactionlayer, ministryrequestid
            )
            if isvalid == True:
                result = redactionservice().getannotationsbyrequest(
                    ministryrequestid, _redactionlayer, page, size
                )
                return result, 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500

@cors_preflight("GET,OPTIONS")
@API.route('/annotation/<int:ministryrequestid>/<string:redactionlayer>/document/<int:documentid>')
class AnnotationDocumentPagination(Resource):
    """ Retrives the foi request based on the queue type.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @cors_preflight('GET,OPTIONS')
    @auth.ismemberofgroups(getrequiredmemberships())
    def get(ministryrequestid, documentid, redactionlayer="redline"):
        try:
            isvalid, _redactionlayer = redactionservice().validateredactionlayer(
                redactionlayer, ministryrequestid
            )
            if isvalid == True:
                result = redactionservice().getannotationsbydocument(
                    ministryrequestid, _redactionlayer, documentid
                )
                return json.dumps(result), 200
        except KeyError as err:
            return {"status": False, "message": err.__str__()}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


@cors_preflight("POST, OPTIONS")
@API.route("/annotation")
class SaveAnnotations(Resource):
    """save or update an annotation for a document"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post():
        try:
            requestjson = request.get_json()
            annotationschema = AnnotationRequest().load(requestjson)
            result = redactionservice().saveannotation(
                annotationschema, AuthHelper.getuserinfo()
            )
            return {
                "status": result.success,
                "message": result.message,
                "annotationid": result.identifier,
            }, 201
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


@cors_preflight("POST,OPTIONS")
@API.route("/annotation/<string:requestid>/<int:redactionlayerid>")
class DeactivateAnnotations(Resource):

    """save or update an annotation for a document"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post(
        requestid,
        redactionlayerid,
    ):
        try:
            requestjson = request.get_json()
            annotationschema = BulkAnnotationRequest().load(requestjson)
            result = redactionservice().deactivateannotation(
                annotationschema,
                AuthHelper.getuserinfo(),
                requestid,
                redactionlayerid,
            )
            return {
                "status": result.success,
                "message": result.message,
                "annotationid": result.identifier,
            }, 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


@cors_preflight("POST,OPTIONS")
@API.route("/redaction/<string:requestid>/<int:redactionlayerid>")
class DeactivateRedactions(Resource):

    """save or update an annotation for a document"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post(requestid, redactionlayerid):
        try:
            requestjson = request.get_json()
            annotationschema = BulkAnnotationRequest().load(requestjson)
            result = redactionservice().deactivateredaction(
                annotationschema,
                AuthHelper.getuserinfo(),
                requestid,
                redactionlayerid,
            )
            return {
                "status": result.success,
                "message": result.message,
                "annotationid": result.identifier,
            }, 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


@cors_preflight("GET,OPTIONS")
@API.route("/annotation/<int:ministryrequestid>/info")
class AnnotationMetadata(Resource):
    """Retrieves annotations for a document"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(ministryrequestid):
        try:
            result = redactionservice().getannotationinfobyrequest(ministryrequestid)
            return json.dumps(result), 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500

@cors_preflight("POST,OPTIONS")
@API.route("/annotation/<int:ministryrequestid>/copy/<string:targetlayer>")
class DeactivateRedactions(Resource):

    """save or update an annotation for a document"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post(ministryrequestid, targetlayer):
        try:
            result = redactionservice().copyannotation(ministryrequestid, targetlayer)
            return {'status': result.success, 'message': result.message }, 200
        except BusinessException as exception:
            return {'status': False, 'message': exception.message }, 500



@cors_preflight("GET,OPTIONS")
@API.route("/redactedsections/ministryrequest/<int:ministryrequestid>")
class GetSections(Resource):
    """Add document to deleted list."""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(ministryrequestid):
        try:
            data = annotationservice().getredactedsectionsbyrequest(ministryrequestid)
            return json.dumps(data), 200
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


@cors_preflight("GET,OPTIONS")
@API.route("/account")
class GetAccount(Resource):
    """Retrieves s3 accounts for user"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get():
        if AuthHelper.getusertype() == "ministry":
            usergroups = AuthHelper.getministrygroups()
            usergroup = usergroups[0]
        else:
            usergroup = AuthHelper.getiaotype()
        try:
            result = redactionservice().gets3serviceaccount(usergroup)
            return json.dumps(result), 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


# added api to trigger the zipping of files for redline
@cors_preflight("POST, OPTIONS")
@API.route("/triggerdownloadredline")
class SaveRedlines(Resource):
    """save redlines for zipping"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post():
        try:
            requestjson = request.get_json()
            redlineschema = RedlineSchema().load(requestjson)
            result = redactionservice().triggerdownloadredlinefinalpackage(
                redlineschema, AuthHelper.getuserinfo()
            )
            return {
                "status": result.success,
                "message": result.message,
            }, 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


# added api to trigger the zipping of files for final package
@cors_preflight("POST, OPTIONS")
@API.route("/triggerdownloadfinalpackage")
class SaveFinalPackage(Resource):
    """save finalpackage for zipping"""

    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post():
        try:
            requestjson = request.get_json()
            finalpackageschema = FinalPackageSchema().load(requestjson)
            result = redactionservice().triggerdownloadredlinefinalpackage(
                finalpackageschema, AuthHelper.getuserinfo()
            )
            return {
                "status": result.success,
                "message": result.message,
            }, 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500
