# Copyright © 2021 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CORS pre-flight decorator.

A simple decorator to add the options method to a Request Class.
"""

import base64
import re
import urllib
from functools import wraps

from humps.main import camelize, decamelize
from flask import request, g
from sqlalchemy.sql.expression import false
from reviewer_api.auth import jwt as _authjwt
import jwt
import os
import json
from reviewer_api.utils.enums import (
    MinistryTeamWithKeycloackGroup,
    ProcessingTeamWithKeycloackGroup,
)
import maya
from reviewer_api.utils.constants import REDLINE_SINGLE_PKG_MINISTRIES, REDLINE_SINGLE_PKG_MINISTRIES_PERSONAL

def cors_preflight(methods):
    # Render an option method on the class.

    def wrapper(f):
        def options(self, *args, **kwargs):  # pylint: disable=unused-argument
            return (
                {"Allow": "GET, DELETE, PUT, POST"},
                200,
                {
                    "Access-Control-Allow-Methods": methods,
                    "Access-Control-Allow-Headers": "Authorization, Content-Type, registries-trace-id, "
                    "invitation_token",
                },
            )

        setattr(f, "options", options)
        return f

    return wrapper


def camelback2snake(camel_dict: dict):
    """Convert the passed dictionary's keys from camelBack case to snake_case."""
    return decamelize(camel_dict)


def snake2camelback(snake_dict: dict):
    """Convert the passed dictionary's keys from snake_case to camelBack case."""
    return camelize(snake_dict)


def getrequiredmemberships():
    membership = ""
    for group in MinistryTeamWithKeycloackGroup:
        membership += "{0},".format(group.value)
    for procgroup in ProcessingTeamWithKeycloackGroup:
        membership += "{0},".format(procgroup.value)
    membership += "Intake Team,Flex Team"
    return membership


def allowedorigins():
    _allowedcors = os.getenv("CORS_ORIGIN")
    allowedcors = []
    if "," in _allowedcors:
        for entry in re.split(",", _allowedcors):
            allowedcors.append(entry)
    return allowedcors


class Singleton(type):
    """Singleton meta."""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Call for meta."""
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def digitify(payload: str) -> int:
    """Return the digits from the string."""
    return int(re.sub(r"\D", "", payload))


def escape_wam_friendly_url(param):
    """Return encoded/escaped url."""
    base64_org_name = base64.b64encode(bytes(param, encoding="utf-8")).decode("utf-8")
    encode_org_name = urllib.parse.quote(base64_org_name, safe="")
    return encode_org_name


def pstformat(dt):
    if dt is not None:
        tolocaltime = maya.MayaDT.from_datetime(dt).datetime(
            to_timezone="America/Vancouver", naive=False
        )
        return tolocaltime.isoformat()
    else:
        return ""

def split(list_a, chunk_size):
        return [list_a[i:i + chunk_size] for i in range(0, len(list_a), chunk_size)]

# converts to json
def to_json(obj):
    return json.dumps(obj, default=lambda obj: obj.__dict__)

def getbatchconfig():
    _batchconfig_str = os.getenv('BATCH_CONFIG',None)
    if _batchconfig_str in (None,''):
        return 2, 100, 250
    _batchconfig = json.loads(_batchconfig_str)
    _begin = _batchconfig["begin"] if "begin" in _batchconfig else 2
    _size =  _batchconfig["size"] if "size" in _batchconfig else 100
    _limit = _batchconfig["limit"] if "limit" in _batchconfig else 250    
    return _begin, _size, _limit

def is_single_redline_package(bcgovcode, packagetype, requesttype):
    if packagetype == "consult":
        return False
    if (packagetype == "oipcreview"):
        return True
    if REDLINE_SINGLE_PKG_MINISTRIES not in (None, ""):
        _pkg_ministries = REDLINE_SINGLE_PKG_MINISTRIES.replace(" ", "").split(',')
        if bcgovcode.upper() in _pkg_ministries:
            return True
    if REDLINE_SINGLE_PKG_MINISTRIES_PERSONAL not in (None, ""):
        _pkg_ministries_personal = REDLINE_SINGLE_PKG_MINISTRIES_PERSONAL.replace(" ", "").split(',')
        if bcgovcode.upper() in _pkg_ministries_personal and requesttype.upper() == "PERSONAL":
            return True
    return False