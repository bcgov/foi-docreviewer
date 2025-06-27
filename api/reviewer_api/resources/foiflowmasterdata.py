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
from flask import request, current_app
from flask_restx import Namespace, Resource
from flask_cors import cross_origin
from reviewer_api.auth import auth, AuthHelper

from reviewer_api.tracer import Tracer
from reviewer_api.utils.util import (
    cors_preflight,
    allowedorigins,
    getrequiredmemberships,
    is_single_redline_package
)
from reviewer_api.exceptions import BusinessException
import json
from aws_requests_auth.aws_auth import AWSRequestsAuth
import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from reviewer_api.services.radactionservice import redactionservice
from reviewer_api.services.documentservice import documentservice
from reviewer_api.utils.constants import FILE_CONVERSION_FILE_TYPES

import requests
import logging

API = Namespace(
    "FOI Flow Master Data", description="Endpoints for FOI Flow master data"
)
TRACER = Tracer.get_instance()
CUSTOM_KEYERROR_MESSAGE = "Key error has occured: "

s3host = os.getenv("OSS_S3_HOST")
s3region = os.getenv("OSS_S3_REGION")
webviewerlicense = os.getenv("PDFTRON_WEBVIEWER_LICENSE")

imageextensions = [".png", ".jpg", ".jpeg", ".gif"]

requestapiurl = os.getenv("FOI_REQ_MANAGEMENT_API_URL")
requestapitimeout = os.getenv("FOI_REQ_MANAGEMENT_API_TIMEOUT")

@cors_preflight("GET,OPTIONS")
@API.route("/foiflow/oss/presigned/<documentid>")
class FOIFlowS3Presigned(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get(documentid):
        try:
            document = documentservice().getdocument(documentid)
            documentmapper = redactionservice().getdocumentmapper(
                document["filepath"].split("/")[3]
            )
            attribute = json.loads(documentmapper["attributes"])

            current_app.logger.debug("Inside Presigned api!!")
            formsbucket = documentmapper["bucket"]
            accesskey = attribute["s3accesskey"]
            secretkey = attribute["s3secretkey"]
            filepath = "/".join(document["filepath"].split("/")[4:])
            s3client = boto3.client(
                "s3",
                config=Config(signature_version="s3v4"),
                endpoint_url="https://{0}/".format(s3host),
                aws_access_key_id=accesskey,
                aws_secret_access_key=secretkey,
                region_name=s3region,
            )

            filename, file_extension = os.path.splitext(filepath)
            response = s3client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": formsbucket,
                    "Key": "{0}".format(filepath),
                    "ResponseContentType": "{0}/{1}".format(
                        "image"
                        if file_extension.lower() in imageextensions
                        else "application",
                        file_extension.replace(".", ""),
                    ),
                },
                ExpiresIn=3600,
                HttpMethod="GET",
            )

            return json.dumps(response), 200
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500

@cors_preflight("POST,OPTIONS")
@API.route("/foiflow/oss/presigned")
class FOIFlowS3PresignedList(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post():
        try:
            data = request.get_json()
            print("\n\nFOIFlowS3PresignedList-Data:",data)
            documentmapper = redactionservice().getdocumentmapper(
                data["documentobjs"][0]["file"]["filepath"].split("/")[3]
            )
            attribute = json.loads(documentmapper["attributes"])

            current_app.logger.debug("Inside Presigned List api!!")
            formsbucket = documentmapper["bucket"]
            s3client = boto3.client(
                "s3",
                config=Config(signature_version="s3v4"),
                endpoint_url="https://{0}/".format(s3host),
                aws_access_key_id=attribute["s3accesskey"],
                aws_secret_access_key=attribute["s3secretkey"],
                region_name=s3region,
            )

            documentobjs = []
            documentids = [documentinfo["file"]["documentid"] for documentinfo in data["documentobjs"]]
            documents = documentservice().getdocumentbyids(documentids)
            print("\n\nFOIFlowS3PresignedList-documents:",documents)
            for documentinfo in data["documentobjs"]:
                print("\n\nFOIFlowS3PresignedList-documentinfo:",documentinfo)
                #s3filepath= documentservice().getdocumentfilepath(documentinfo)
                filepath = "/".join(documents[documentinfo["file"]["documentid"]].split("/")[4:])
                print("\n\nFOIFlowS3PresignedList-filepath:",filepath)
                filename, file_extension = os.path.splitext(filepath)
                documentinfo["s3url"] = s3client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": formsbucket,
                        "Key": "{0}".format(filepath),
                        "ResponseContentType": "{0}/{1}".format(
                            "image"
                            if file_extension.lower() in imageextensions
                            else "application",
                            file_extension.replace(".", ""),
                        ),
                    },
                    ExpiresIn=3600,
                    HttpMethod="GET",
                )
                documentobjs.append(documentinfo)

            return json.dumps(documentobjs), 200
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500

@cors_preflight("POST,OPTIONS")
@API.route("/foiflow/oss/presigned/<redactionlayer>/<int:ministryrequestid>/<string:layertype>")
@API.route("/foiflow/oss/presigned/<redactionlayer>/<int:ministryrequestid>/<string:layertype>/<int:phase>")
class FOIFlowS3PresignedRedline(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(ministryrequestid, redactionlayer="redline", layertype="redline", phase=None):
        try:            
            data = request.get_json()
            # print("data!:",data)
            requesttype = data["requestType"]
            documentmapper = redactionservice().getdocumentmapper(
                data["divdocumentList"][0]["documentlist"][0]["filepath"].split("/")[3]
            )
            attribute = json.loads(documentmapper["attributes"])

            # current_app.logger.debug("Inside Presigned api!!")
            formsbucket = documentmapper["bucket"]
            accesskey = attribute["s3accesskey"]
            secretkey = attribute["s3secretkey"]
            s3client = boto3.client(
                "s3",
                config=Config(signature_version="s3v4"),
                endpoint_url="https://{0}/".format(s3host),
                aws_access_key_id=accesskey,
                aws_secret_access_key=secretkey,
                region_name=s3region,
            )
            _bcgovcode = formsbucket.split("-")[0]
            singlepkgpath = None
            #New Logic - Begin
            filepaths = []

            # set type of package based off redline and layer
            packagetype = "redline"
            if redactionlayer == "oipc":
                packagetype = "oipcreview" if layertype == "oipcreview" else "oipcredline"
            if layertype == "consult":
                packagetype = "consult"
            
            #check if is single redline package
            is_single_redline = is_single_redline_package(_bcgovcode, packagetype, requesttype)
            # print("is_single_redline:",is_single_redline)
            #print("divdocumentList:",data["divdocumentList"])
            for div in data["divdocumentList"]:
                if len(div["documentlist"]) > 0:
                    # print("filepathlist:" , div["documentlist"][0]["filepath"])
                    filepathlist = div["documentlist"][0]["filepath"].split("/")[4:]
                    if is_single_redline == False:
                        division_name = div["divisionname"]
                        # generate save url for stitched file
                        filepath_put = "{0}/{2}/{1}/{0} - {2} - {1}.pdf".format(
                            filepathlist[0], division_name, packagetype
                        )
                        if packagetype == "redline" and phase is not None:
                            filepath_put = "{0}/{3}/{1}/{0} - {2} - {1}.pdf".format(
                                filepathlist[0], division_name, f"Redline - Phase {phase}", f"{packagetype}_phase{phase}"
                            )
                        if packagetype == "consult":
                            filepath_put = "{0}/{2}/{2} - {1} - {0}.pdf".format(
                                filepathlist[0], division_name, 'Consult'
                            )
                        s3path_save = s3client.generate_presigned_url(
                            ClientMethod="get_object",
                            Params={
                                "Bucket": formsbucket,
                                "Key": "{0}".format(filepath_put),
                                "ResponseContentType": "application/pdf",
                            },
                            ExpiresIn=3600,
                            HttpMethod="PUT",
                        )

                            # for save/put - stitch by division
                        div["s3path_save"] = s3path_save
                    for doc in div["documentlist"]:
                        realfilepath = documentservice().getfilepathbydocumentid(doc["documentid"])
                        # filepathlist = doc["filepath"].split("/")[4:]
                        filepathlist = realfilepath.split("/")[4:]
                        
                        # for load/get
                        filepath_get = "/".join(filepathlist)
                        
                        filename_get, file_extension_get = os.path.splitext(
                                        filepath_get
                            )
                        originalextensions = ['.pdf']
                        originalextensions.extend(imageextensions)
                        file_extension_get = (
                                        file_extension_get.replace(".", "")
                                        if file_extension_get.lower() in originalextensions
                                        else "pdf"
                                )
                        doc["s3path_load"] = s3client.generate_presigned_url(
                                        ClientMethod="get_object",
                                        Params={
                                            "Bucket": formsbucket,
                                            "Key": "{0}.{1}".format(
                                                filename_get, file_extension_get
                                            ),
                                            "ResponseContentType": "{0}/{1}".format(
                                                "image"
                                                if file_extension_get.lower() in imageextensions
                                                else "application",
                                                file_extension_get,
                                            ),
                                        },
                                        ExpiresIn=3600,
                                        HttpMethod="GET",
                                    )
                elif len(div["incompatableList"]) > 0:
                    filepathlist = div["incompatableList"][0]["filepath"].split("/")[4:]
                if is_single_redline and singlepkgpath is None :
                    if len(div["documentlist"]) > 0 or len(div["incompatableList"]) > 0:
                        div = data["divdocumentList"][0] 
                        filepathlist = div["documentlist"][0]["filepath"].split("/")[4:]
                        # print("filepathlist:",filepathlist)
                        filename = filepathlist[0]
                        # print("filename1:",filename)
                        if packagetype == "redline" and phase is not None:
                            filepath_put = "{0}/{2}/{1} - {3}.pdf".format(
                                filepathlist[0],filename, f"{packagetype}_phase{phase}", f"Redline - Phase {phase}"
                            )
                        else:
                            filepath_put = "{0}/{2}/{1} - Redline.pdf".format(
                                filepathlist[0],filename, packagetype
                            )
                        # print("filepath_put:",filepath_put)
                        s3path_save = s3client.generate_presigned_url(
                            ClientMethod="get_object",
                            Params={
                            "Bucket": formsbucket,
                            "Key": "{0}".format(filepath_put),
                            "ResponseContentType": "application/pdf",
                            },
                            ExpiresIn=3600,
                            HttpMethod="PUT",
                        )
                        # print("s3path_save:",s3path_save)
                        singlepkgpath = s3path_save
                        data["s3path_save"] = s3path_save
                        
            if is_single_redline:
                for div in data["divdocumentList"]:
                    if len(div["documentlist"]) > 0:
                        documentlist_copy = div["documentlist"][:]
                        for doc in documentlist_copy:
                            if doc["filepath"] not in filepaths:
                                filepaths.append(doc["filepath"])
                            else:
                                div["documentlist"].remove(doc)
                    if len(div["incompatableList"]) > 0:
                        incompatiblelist_copy = div["incompatableList"][:]
                        for incompatible in incompatiblelist_copy:
                            if incompatible["filepath"] not in filepaths:
                                filepaths.append(incompatible["filepath"])
                            else:
                                div["incompatableList"].remove(incompatible)
                    
            data["requestnumber"] = filepathlist[0]
            data["bcgovcode"] = _bcgovcode
            data["issingleredlinepackage"] = "Y" if is_single_redline else "N"
            return json.dumps(data), 200
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500




@cors_preflight("POST,OPTIONS")
@API.route("/foiflow/oss/presigned/responsepackage/<int:ministryrequestid>")
class FOIFlowS3PresignedResponsePackage(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(ministryrequestid):
        try:
            json_data = request.get_json()
            data = json_data["documentsInfo"]
            phase = json_data["phase"]
            documentmapper = redactionservice().getdocumentmapper(
                data["filepath"].split("/")[3]
            )
            attribute = json.loads(documentmapper["attributes"])

            # current_app.logger.debug("Inside Presigned api!!")
            formsbucket = documentmapper["bucket"]
            accesskey = attribute["s3accesskey"]
            secretkey = attribute["s3secretkey"]
            s3client = boto3.client(
                "s3",
                config=Config(signature_version="s3v4"),
                endpoint_url="https://{0}/".format(s3host),
                aws_access_key_id=accesskey,
                aws_secret_access_key=secretkey,
                region_name=s3region,
            )

            # generate save url for stitched file
            filepathlist = data["filepath"].split("/")[4:]
            filename = filepathlist[0]
            if phase is not None:
                filepath_put = "{0}/{2}/{1} - {3}.pdf".format(
                    filepathlist[0], filename,f"responsepackage_phase{phase}",f"Phase {phase}")
            else:
                filepath_put = "{0}/responsepackage/{1}.pdf".format(
                    filepathlist[0], filename
            )

            # filename_put, file_extension_put = os.path.splitext(filepath_put)
            # filepath_put = filename_put+'.pdf'
            s3path_save = s3client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": formsbucket,
                    "Key": "{0}".format(filepath_put),
                    "ResponseContentType": "application/pdf",
                },
                ExpiresIn=3600,
                HttpMethod="PUT",
            )

            # for save/put - stitch by division
            data["s3path_save"] = s3path_save
            data["requestnumber"] = filepathlist[0]
            data["bcgovcode"] = formsbucket.split("-")[0]

            return json.dumps(data), 200
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500

@cors_preflight("POST,OPTIONS")
@API.route("/foiflow/webviewerlicense")
class WebveiwerLicense(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.hasusertype('iao')
    def get():
        try:
            return json.dumps({"license": webviewerlicense}), 200
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500


@cors_preflight('GET,OPTIONS')
@API.route('/foiflow/personalattributes/<bcgovcode>')
class GetPersonalTags(Resource):
    """Get document list.
    """
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def get(bcgovcode):
        try:
            attributes = ["people", "filetypes", "volumes", "personaltag"]
            personalattributes = {}

            for attribute in attributes:
                response = requests.request(
                    method='GET',
                    url= requestapiurl + "/api/foiflow/divisions/" + bcgovcode + "/true/" + attribute,
                    headers={'Authorization': AuthHelper.getauthtoken(), 'Content-Type': 'application/json'},
                    timeout=float(requestapitimeout)
                )
                response.raise_for_status()
                # get request status
                jsonobj = response.json()
                personalattributes.update(jsonobj)

            return json.dumps(personalattributes), 200
        except KeyError as error:
            return {'status': False, 'message': CUSTOM_KEYERROR_MESSAGE + str(error)}, 400
        except BusinessException as exception:
            return {'status': exception.status_code, 'message':exception.message}, 500
        except requests.exceptions.HTTPError as err:
            logging.error("Request Management API returned the following message: {0} - {1}".format(err.response.status_code, err.response.text))
            return {'status': False, 'message': err.response.text}, err.response.status_code