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

# from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
import json
import os

from reviewer_api.services.radactionservice import redactionservice
from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.schemas.annotationrequest import AnnotationRequest, SectionRequestSchema, SectionSchema
from marshmallow import ValidationError, EXCLUDE


API = Namespace('Document and annotations', description='Endpoints for document and annotation operations')
# TRACER = Tracer.get_instance()



@cors_preflight('GET,POST, OPTIONS')
@API.route('/annotation/<int:documentid>/<int:documentversion>')
@API.route('/annotation/<int:documentid>/<int:documentversion>/<int:pagenumber>')
@API.route('/annotation/<int:documentid>/<int:documentversion>/<int:pagenumber>/<string:annotationname>')
class Annotations(Resource):
    """Retrieves annotations for a document
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(documentid, documentversion, pagenumber=None):
        try:
            result = redactionservice().getannotations(documentid, documentversion, pagenumber)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


    """save or update an annotation for a document
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post(documentid, documentversion, pagenumber, annotationname):
        try:
            requestjson = request.get_json()
            annotationschema = AnnotationRequest().load(requestjson)
            result = redactionservice().saveannotation(annotationname, documentid, documentversion, annotationschema, pagenumber, AuthHelper.getuserinfo())
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 201
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('DELETE,OPTIONS')
@API.route('/annotation/<int:documentid>/<int:documentversion>/<string:annotationname>')
class DeactivateAnnotations(Resource):
    
    """save or update an annotation for a document
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def delete(documentid, documentversion, annotationname):
        
        try:
            result = redactionservice().deactivateannotation(annotationname, documentid, documentversion, AuthHelper.getuserinfo())
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
        

@cors_preflight('DELETE,OPTIONS')
@API.route('/annotation/<int:documentid>/<int:documentversion>/<string:annotationname>')
class DeactivateAnnotations(Resource):
    
    """save or update an annotation for a document
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def delete(documentid, documentversion, annotationname):
        
        try:
            result = redactionservice().deactivateannotation(annotationname, documentid, documentversion, AuthHelper.getuserinfo())
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500

@cors_preflight('POST,OPTIONS')
@API.route('/annotation/section/<string:sectionannotationname>')
class AnnotationSections(Resource):
    
    """save or update an annotation for a document
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def post(sectionannotationname):
        try:
            requestjson = request.get_json()
            sectionschema = SectionRequestSchema().load(requestjson)
            result = annotationservice().saveannotationsection(sectionannotationname, sectionschema, AuthHelper.getuserinfo())
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 201
        except ValidationError as err:
            return {"errors": err.messages}, 422
        except ValueError as err:
            return {'status': 500, 'message':err.messages}, 500
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,POST,DELETE,OPTIONS')
@API.route('/annotation/<int:documentid>/<int:documentversion>/info')
@API.route('/annotation/<int:documentid>/<int:documentversion>/<int:pagenumber>/info')
@API.route('/annotation/<int:documentid>/<int:documentversion>/<int:pagenumber>/<string:annotationname>/info')
class AnnotationMetadata(Resource):
    """Retrieves annotations for a document
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(documentid, documentversion, pagenumber=None):
        try:
            result = redactionservice().getannotationinfo(documentid, documentversion, pagenumber)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500



@cors_preflight('GET,OPTIONS')
@API.route('/account')
class GetAccount(Resource):
    """Retrieves s3 accounts for user
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get():
        if AuthHelper.getusertype() == "ministry":
            usergroups = AuthHelper.getministrygroups()
            usergroup = usergroups[0]
        else:
            usergroup = AuthHelper.getiaotype()

        print(usergroup)
        try:
            # redactionservice().gets3serviceaccount('test')
            result = redactionservice().gets3serviceaccount(usergroup)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


