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
"""Bring in the common JWT Manager."""
from functools import wraps
from http import HTTPStatus

from flask import g, request
from flask_jwt_oidc import JwtManager
from jose import JWTError, jwt as josejwt
from reviewer_api.utils.enums import (
    MinistryTeamWithKeycloackGroup,
    ProcessingTeamWithKeycloackGroup,
    IAOTeamWithKeycloackGroup,
) 

jwt = (
    JwtManager()
)  # pylint: disable=invalid-name; lower case name as used by convention in most Flask apps


class Auth:
    """Extending JwtManager to include additional functionalities."""

    @classmethod
    def require(cls, f):
        """Validate the Bearer Token."""

        @jwt.requires_auth
        @wraps(f)
        def decorated(*args, **kwargs):
            g.authorization_header = request.headers.get("Authorization", None)
            g.token_info = g.jwt_oidc_token_info
            return f(*args, **kwargs)

        return decorated

    @classmethod
    def hasusertype(cls, usertype):
        def decorated(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                if usertype == AuthHelper.getusertype():
                    return f(*args, **kwargs)
                return "Unauthorized", 401

            return wrapper

        return decorated

    @classmethod
    def ismemberofgroups(cls, groups):
        """Check that at least one of the realm groups are in the token.
        Args:
            groups [str,]: Comma separated list of valid roles
        """

        def decorated(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                _groups = groups.split(",")
                token = jwt.get_token_auth_header()
                unverified_claims = josejwt.get_unverified_claims(token)
                usergroups = unverified_claims["groups"]
                usergroups = [
                    usergroup.replace("/", "", 1)
                    if usergroup.startswith("/")
                    else usergroup
                    for usergroup in usergroups
                ]
                exists = False
                for group in _groups:
                    if group in usergroups:
                        exists = True
                retval = "Unauthorized", 401
                if exists == True:
                    return f(*args, **kwargs)
                return retval

            return wrapper

        return decorated


auth = Auth()


class AuthHelper:
    @classmethod
    def getuserid(cls, token=None):
        try:
            if token is None:
                token = request.headers.get("Authorization", None)
            unverified_claims = josejwt.get_unverified_claims(
                token.partition("Bearer")[2].strip()
            )
            claim_name = (
                "foi_preferred_username"
                if "foi_preferred_username" in unverified_claims
                else "preferred_username"
            )
            claim_value = unverified_claims[claim_name].lower()
            return (
                claim_value + "@idir"
                if claim_value.endswith("@idir") == False
                else claim_value
            )

        except JWTError as exception:
            print("JWTError >>> ", str(exception))
        except Exception as ex:
            print("Exception >>> ", str(ex))

    @classmethod
    def getwsuserid(cls, token):
        unverified_claims = josejwt.get_unverified_claims(token.strip())
        return unverified_claims["preferred_username"]

    @classmethod
    def getusername(cls):
        token = request.headers.get("Authorization", None)
        unverified_claims = josejwt.get_unverified_claims(
            token.partition("Bearer")[2].strip()
        )
        return unverified_claims["name"]

    @classmethod
    def isministrymember(cls):
        usergroups = cls.getusergroups()
        ministrygroups = list(
            set(usergroups).intersection(MinistryTeamWithKeycloackGroup.list())
        )
        if len(ministrygroups) > 0:
            return True
        return False

    @classmethod
    def isprocesingteammember(cls):
        usergroups = cls.getusergroups()
        ministrygroups = list(
            set(usergroups).intersection(MinistryTeamWithKeycloackGroup.list())
        )
        if len(ministrygroups) > 0:
            return False
        else:
            processinggroups = list(
                set(usergroups).intersection(ProcessingTeamWithKeycloackGroup.list())
            )
            if len(processinggroups) > 0:
                return True
        return False

    @classmethod
    def getusergroups(cls):
        token = request.headers.get("Authorization", None)
        unverified_claims = josejwt.get_unverified_claims(
            token.partition("Bearer")[2].strip()
        )
        usergroups = unverified_claims["groups"]
        usergroups = [
            usergroup.replace("/", "", 1) if usergroup.startswith("/") else usergroup
            for usergroup in usergroups
        ]
        return usergroups

    @classmethod
    def getusertype(cls):
        usergroups = cls.getusergroups()
        ministrygroups = list(
            set(usergroups).intersection(MinistryTeamWithKeycloackGroup.list())
        )
        if len(ministrygroups) > 0:
            return "ministry"
        else:
            iaogroups = list(
                set(usergroups).intersection(IAOTeamWithKeycloackGroup.list())
            )
            if len(iaogroups) > 0:
                return "iao"
        return None

    @classmethod
    def getiaotype(cls):
        usergroups = cls.getusergroups()
        _groups = set(usergroups)
        if cls.isministrymember() == False:
            processinggroups = list(
                _groups.intersection(ProcessingTeamWithKeycloackGroup.list())
            )
            if len(processinggroups) > 0:
                return "processing"
            else:
                if "Flex Team" in _groups:
                    return "flex"
                elif "Intake Team" in _groups:
                    return "intake"
                else:
                    return None
        else:
            return None

    @classmethod
    def getministrygroups(cls):
        usergroups = cls.getusergroups()
        return list(set(usergroups).intersection(MinistryTeamWithKeycloackGroup.list()))

    @classmethod
    def getfirstname(cls):
        token = request.headers.get("Authorization", None)
        unverified_claims = josejwt.get_unverified_claims(
            token.partition("Bearer")[2].strip()
        )
        return unverified_claims["given_name"]

    @classmethod
    def getlastname(cls):
        token = request.headers.get("Authorization", None)
        unverified_claims = josejwt.get_unverified_claims(
            token.partition("Bearer")[2].strip()
        )
        return unverified_claims["family_name"]

    @classmethod
    def getuserinfo(cls):
        # get user info
        if cls.getusertype() == "ministry":
            usergroups = cls.getministrygroups()
            usergroup = usergroups[0]
        else:
            usergroup = cls.getiaotype()

        return {
            "userid": cls.getuserid(),
            "firstname": cls.getfirstname(),
            "lastname": cls.getlastname(),
            "operatingteam": usergroup,
        }

    @classmethod
    def getauthtoken(cls):
        return request.headers.get("Authorization", None)
