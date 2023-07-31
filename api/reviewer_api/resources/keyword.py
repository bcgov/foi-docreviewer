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

from reviewer_api.services.keywordservice import keywordservice
import json

API = Namespace('Keywords Services', description='Endpoints for Keyword management')

@cors_preflight('GET,OPTIONS')
@API.route('/keywords')
class GetSections(Resource):
    """Get all Keywords list.
    """
    @staticmethod
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get():
        try:
            data = keywordservice().getallkeywords()
            return json.dumps(data) , 200
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
