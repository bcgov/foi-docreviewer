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

from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from reviewer_api.exceptions import BusinessException

from reviewer_api.services.pageflagservice import pageflagservice
import json

API = Namespace('Pageflag Services', description='Endpoints for Pageflag management')

@cors_preflight('GET,OPTIONS')
@API.route('/pageflags')
class GetSections(Resource):
    """Get Pageflags list.
    """
    @staticmethod
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get():
        try:
            data = pageflagservice().getpageflags()
            return json.dumps(data) , 200
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/pageflags/ministryrequest/<requestid>/<string:redactionlayer>')
class GetSections(Resource):
    """Get Pageflags list.
    """
    @staticmethod
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get(requestid, redactionlayer):
        try:
            data = pageflagservice().getpageflag_by_request(requestid, redactionlayer)
            return json.dumps(data) , 200
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500