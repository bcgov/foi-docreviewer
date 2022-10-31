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
from api.reviewer_api.auth import Auth
from flask import request, current_app
from flask_restx import Namespace, Resource
from flask_cors import cross_origin
from reviewer_api.auth import auth, AuthHelper

# from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
import json
import os
from reviewer_api.auth import AuthHelper
from reviewer_api.services.radactionservice import redactionservice
from reviewer_api.schemas.annotationrequest import AnnotationRequest

from flask import jsonify

API = Namespace('Redaction App Master Data', description='Endpoints for Redaction app master data')
# TRACER = Tracer.get_instance()

@cors_preflight('GET,OPTIONS')
@API.route('/document/<requestid>')
class GetDocuments(Resource):
    """Get document list.
    """
    @staticmethod
    # @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    # @auth.ismemberofgroups(getrequiredmemberships())
    def get(requestid):
        try:
            result = redactionservice().getdocuments(requestid)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,POST,DELETE,OPTIONS')
@API.route('/annotation/<documentid>/<documentversion>')
@API.route('/annotation/<documentid>/<documentversion>/<pagenumber>')
@API.route('/annotation/<documentid>/<documentversion>/<pagenumber>/<annotationname>')
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

        #get user info
        if AuthHelper.getusertype() == "ministry":
            usergroups = AuthHelper.getministrygroups()
            usergroup = usergroups[0]
        else:
            usergroup = AuthHelper.getiaotype()

        userinfo = {
            'userid': AuthHelper.getuserid(),
            'firstname': AuthHelper.getfirstname(),
            'lastname': AuthHelper.getlastname(),
            'operatingteam': usergroup
        }

        try:
            requestjson = request.get_json()
            annotationschema = AnnotationRequest.load(requestjson)

            result = redactionservice().saveannotation(annotationname, documentid, documentversion, annotationschema['xml'], pagenumber, userinfo)
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 201
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
    def delete(documentid, documentversion, annotationname):
        #get user info
        if AuthHelper.getusertype() == "ministry":
            usergroups = AuthHelper.getministrygroups()
            usergroup = usergroups[0]
        else:
            usergroup = AuthHelper.getiaotype()

        userinfo = {
            'userid': AuthHelper.getuserid(),
            'firstname': AuthHelper.getfirstname(),
            'lastname': AuthHelper.getlastname(),
            'operatingteam': usergroup
        }

        try:
            result = redactionservice().deactivateannotation(annotationname, documentid, documentversion, userinfo)
            return {'status': result.success, 'message':result.message, 'annotationid':result.identifier}, 200
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
            result = redactionservice().gets3serviceaccount(usergroup)
            return json.dumps(result), 200
        except KeyError as err:
            return {'status': False, 'message':err.messages}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


