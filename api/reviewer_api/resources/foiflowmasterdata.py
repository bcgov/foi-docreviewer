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

API = Namespace(
    "FOI Flow Master Data", description="Endpoints for FOI Flow master data"
)
TRACER = Tracer.get_instance()

s3host = os.getenv("OSS_S3_HOST")
s3region = os.getenv("OSS_S3_REGION")
webviewerlicense = os.getenv("PDFTRON_WEBVIEWER_LICENSE")

imageextensions = [".png", ".jpg", ".jpeg", ".gif"]


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
            for documentinfo in data["documentobjs"]:
                filepath = "/".join(documents[documentinfo["file"]["documentid"]].split("/")[4:])
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

"""
@cors_preflight("POST,OPTIONS")
@API.route("/foiflow/oss/presigned/redline/<int:ministryrequestid>")
class FOIFlowS3PresignedRedline(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(ministryrequestid):
        try:
            data = request.get_json()
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
            for div in data["divdocumentList"]:
                if len(div["documentlist"]) > 0:
                    division_name = div["documentlist"][0]["divisions"][0]["name"]
                    # generate save url for stitched file
                    filepathlist = div["documentlist"][0]["filepath"].split("/")[4:]
                    filepath_put = "{0}/redline/{1}/{0} - Redline - {1}.pdf".format(
                        filepathlist[0], division_name
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
                    div["s3path_save"] = s3path_save

                    # retrieve annotations for stitch by division
                    div[
                        "annotationXML"
                    ] = redactionservice().getannotationsbyrequestdivision(
                        ministryrequestid, div["divisionid"]
                    )

                    for doc in div["documentlist"]:
                        filepathlist = doc["filepath"].split("/")[4:]

                        # for load/get
                        filepath_get = "/".join(filepathlist)
                        filename_get, file_extension_get = os.path.splitext(
                            filepath_get
                        )
                        file_extension_get = (
                            file_extension_get.replace(".", "")
                            if file_extension_get.lower() in imageextensions
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
            data["requestnumber"] = filepathlist[0]
            data["bcgovcode"] = formsbucket.split("-")[0]
            return json.dumps(data), 200
        except BusinessException as exception:
            return {"status": exception.status_code, "message": exception.message}, 500
"""

@cors_preflight("POST,OPTIONS")
@API.route("/foiflow/oss/presigned/redline/<int:ministryrequestid>")
class FOIFlowS3PresignedRedline(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(ministryrequestid):
        try:            
            data = request.get_json()
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
            singlepkgpath = None;
            #New Logic - Begin
            filepaths = []
            for div in data["divdocumentList"]:
                if len(div["documentlist"]) > 0:
                    filepathlist = div["documentlist"][0]["filepath"].split("/")[4:]
                    if is_single_redline_package(_bcgovcode) == False:
                        division_name = div["divisionname"]
                        # generate save url for stitched file
                        filepath_put = "{0}/redline/{1}/{0} - Redline - {1}.pdf".format(
                            filepathlist[0], division_name
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
                        div["s3path_save"] = s3path_save
                    for doc in div["documentlist"]:
                        filepathlist = doc["filepath"].split("/")[4:]
                        # for load/get
                        filepath_get = "/".join(filepathlist)
                        filename_get, file_extension_get = os.path.splitext(
                                        filepath_get
                            )
                        file_extension_get = (
                                        file_extension_get.replace(".", "")
                                        if file_extension_get.lower() in imageextensions
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
                if is_single_redline_package(_bcgovcode) and singlepkgpath is None :                        
                    if len(div["documentlist"]) > 0 or len(div["incompatableList"]) > 0:
                        div = data["divdocumentList"][0] 
                        filepathlist = div["documentlist"][0]["filepath"].split("/")[4:]
                        filename = filepathlist[0]
                        filepath_put = "{0}/redline/{1}-Redline.pdf".format(
                            filepathlist[0],filename
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
                        singlepkgpath = s3path_save
                        data["s3path_save"] = s3path_save
                    
            if is_single_redline_package(_bcgovcode):
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
            data["issingleredlinepackage"] = "Y" if is_single_redline_package(_bcgovcode) else "N"
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
            data = request.get_json()
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
