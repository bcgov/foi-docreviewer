from flask import request, jsonify
from flask_restx import Resource, Namespace
from reviewer_api.services.bcgovidirservice import bcgovidirservice
from reviewer_api.auth import auth, AuthHelper
from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import  cors_preflight, allowedorigins, getrequiredmemberships
from flask_cors import cross_origin

API = Namespace('bcgovidir', description='BCGovIDIR operations')
TRACER = Tracer.get_instance()
@API.route('/bcgovidir/check')
class BCGovIDIRCheck(Resource):
    
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(self):
        """
        Accepts a JSON array of sAMAccountName strings and returns matching records.
        Example request body: ["user1", "user2", "user3"]
        """
        try:
            data = request.get_json()
            if not isinstance(data, list):
                return {"error": "Request body must be a list of sAMAccountName strings."}, 400

            results = bcgovidirservice().get_idirs_by_samaccountnames(data)
            # Convert results to dicts if needed
            return jsonify([{"sAMAccountName": idir.sAMAccountName} for idir in results])
        except Exception as ex:
            return {"error": str(ex)}, 500