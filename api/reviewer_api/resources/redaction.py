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
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
import json
import os
from reviewer_api.services.radactionservice import redactionservice
from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.schemas.annotationrequest import AnnotationRequest, SectionRequestSchema, SectionSchema
from marshmallow import ValidationError, EXCLUDE

API = Namespace('Document and annotations', description='Endpoints for document and annotation operations')
TRACER = Tracer.get_instance()

@cors_preflight('GET,OPTIONS')
@API.route('/annotation/<int:ministryrequestid>')
class Annotations(Resource):
    """Retrieves annotations for a document
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get(ministryrequestid):
        try:
            result = redactionservice().getannotationsbyrequest(ministryrequestid)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('POST, OPTIONS')
@API.route('/annotation/<int:documentid>/<int:documentversion>')
class SaveAnnotations(Resource):
    """save or update an annotation for a document
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post(documentid, documentversion):
        try:
            requestjson = request.get_json()
            annotationschema = AnnotationRequest().load(requestjson)
            result = redactionservice().saveannotation(documentid, documentversion, annotationschema, AuthHelper.getuserinfo())
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 201
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('DELETE,OPTIONS')
@API.route('/annotation/<string:requestid>/<int:documentid>/<int:documentversion>/<string:annotationname>/<string:freezepageflags>', defaults={'page':None})
@API.route('/annotation/<string:requestid>/<int:documentid>/<int:documentversion>/<string:annotationname>/<string:freezepageflags>/<int:page>')
class DeactivateAnnotations(Resource):
    
    """save or update an annotation for a document
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def delete(requestid, documentid, documentversion, annotationname, freezepageflags, page:None):
        
        try:
            result = redactionservice().deactivateannotation(annotationname, documentid, documentversion, AuthHelper.getuserinfo(), requestid, page, freezepageflags)
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 200
        except KeyError as err:
            return {'status': False, 'message':err.message}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('DELETE,OPTIONS')
@API.route('/redaction/<string:requestid>/<int:documentid>/<int:documentversion>/<string:annotationname>/<string:freezepageflags>/<int:page>')
class DeactivateRedactions(Resource):
    
    """save or update an annotation for a document
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def delete(requestid, documentid, documentversion, annotationname, freezepageflags, page):
        
        try:
            result = redactionservice().deactivateredaction(annotationname, documentid, documentversion, AuthHelper.getuserinfo(), requestid, page, freezepageflags)
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 200
        except KeyError as err:
            return {'status': False, 'message':err.message}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
        

@cors_preflight('GET,OPTIONS')
@API.route('/annotation/<int:ministryrequestid>/info')
class AnnotationMetadata(Resource):
    """Retrieves annotations for a document
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(ministryrequestid):
        try:
            result = redactionservice().getannotationinfobyrequest(ministryrequestid)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/redactedsections/ministryrequest/<int:ministryrequestid>')
class GetSections(Resource):
    """Add document to deleted list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(ministryrequestid):
        try:
            data = annotationservice().getredactedsectionsbyrequest(ministryrequestid)
            return json.dumps(data) , 200
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/account')
class GetAccount(Resource):
    """Retrieves s3 accounts for user
    """
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
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


