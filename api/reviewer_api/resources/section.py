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
"""API endpoints for managing a FOI Sections resource."""

from flask_restx import Namespace, Resource
from flask_cors import cross_origin
from flask import request
from reviewer_api.auth import auth

from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException

from reviewer_api.services.sectionservice import sectionservice
import json

API = Namespace('Section Services', description='Endpoints for sections management')
TRACER = Tracer.get_instance()

@cors_preflight('GET,OPTIONS')
@API.route('/sections')
class GetSections(Resource):
    """Add document to deleted list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get():
        try:
            data = sectionservice().getsections()
            return json.dumps(data) , 200
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/sections/ministryrequest/<int:ministryrequestid>/<string:redactionlayer>')
class GetSections(Resource):
    """Add document to deleted list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    def get(ministryrequestid, redactionlayer):
        try:
            data = sectionservice().getsections_by_ministryid(ministryrequestid, redactionlayer)
            return json.dumps(data) , 200
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
