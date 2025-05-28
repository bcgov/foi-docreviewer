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
from flask import  request, jsonify

from reviewer_api.auth import auth, AuthHelper
from os import getenv

from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException
import json
import requests
import logging
from reviewer_api.services.redlineconentservice import redlinecontentservice


API = Namespace('Redline Content Services', description='Endpoints for saving REDLINE Content with FOIPPA Sections')
TRACER = Tracer.get_instance()
CUSTOM_KEYERROR_MESSAGE = "Key error has occured: "



@cors_preflight('POST,OPTIONS')
@API.route('/redlinecontent/save/<int:ministryrequestid>')
class RedlineContent(Resource):
    """Add document to deleted list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(ministryrequestid):
        try:
            data = request.get_json()
            if not isinstance(data, list):
                return jsonify({'error': 'Expected a list of redline content objects'}), 400
           
            result = redlinecontentservice().save_redline_content(data, createdby=AuthHelper.getuserid(),ministryrequestid=ministryrequestid)
            return jsonify({'status': 'success', 'result': result}), 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500