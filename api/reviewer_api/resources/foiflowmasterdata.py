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
import base64

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

        if not documentid:
            return {"message": "documentid is required"}, 400

        try:
            document = documentservice().getdocument(documentid)

            if not document:
                return {"message": "Document not found"}, 404

            filepath = document.get("filepath")
            if not filepath:
                return {"message": "Document has no associated file"}, 400

            path_parts = filepath.split("/")
            if len(path_parts) < 5:
                current_app.logger.warning(
                    "Invalid filepath format",
                    extra={"documentid": documentid, "filepath": filepath},
                )
                return {"message": "Invalid document filepath"}, 400

            mapper_key = path_parts[3]

            documentmapper = redactionservice().getdocumentmapper(mapper_key)
            if not documentmapper:
                return {"message": "Document mapper not found"}, 404

            attributes_raw = documentmapper.get("attributes")
            if not attributes_raw:
                return {"message": "Document mapper attributes missing"}, 500

            try:
                attributes = json.loads(attributes_raw)
            except json.JSONDecodeError:
                current_app.logger.error(
                    "Invalid document mapper attributes JSON",
                    extra={"documentid": documentid},
                )
                return {"message": "Invalid document mapper configuration"}, 500

            formsbucket = documentmapper.get("bucket")
            accesskey = attributes.get("s3accesskey")
            secretkey = attributes.get("s3secretkey")

            if not all([formsbucket, accesskey, secretkey]):
                current_app.logger.error(
                    "Missing S3 configuration",
                    extra={"documentid": documentid},
                )
                return {"message": "S3 configuration incomplete"}, 500

            object_key = "/".join(path_parts[4:])
            if not object_key:
                return {"message": "Invalid S3 object key"}, 400

            filename, file_extension = os.path.splitext(object_key)
            content_type = "{}/{}".format(
                "image" if file_extension.lower() in imageextensions else "application",
                file_extension.replace(".", ""),
            )

            s3client = boto3.client(
                "s3",
                config=Config(signature_version="s3v4"),
                endpoint_url=f"https://{s3host}/",
                aws_access_key_id=accesskey,
                aws_secret_access_key=secretkey,
                region_name=s3region,
            )

            presigned_url = s3client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": formsbucket,
                    "Key": object_key,
                    "ResponseContentType": content_type,
                },
                ExpiresIn=3600,
                HttpMethod="GET",
            )

            return presigned_url, 200

        except BusinessException as e:
            current_app.logger.warning(
                "Business exception generating presigned URL",
                extra={"documentid": documentid, "error": str(e)},
            )
            return {"message": e.message}, e.status_code

        except Exception as e:
            current_app.logger.exception(
                "Unhandled error generating presigned URL",
                extra={"documentid": documentid},
            )
            return {"message": "Failed to generate presigned URL"}, 500


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
            data = request.get_json(silent=True)

            if not data or "documentobjs" not in data or not data["documentobjs"]:
                return {"message": "documentobjs is required"}, 400

            documentobjs_input = data["documentobjs"]

            # ---- Validate first document (used to resolve mapper) ----
            first_file = documentobjs_input[0].get("file")
            if not first_file or not first_file.get("filepath"):
                return {"message": "Invalid document file metadata"}, 400

            path_parts = first_file["filepath"].split("/")
            if len(path_parts) < 5:
                return {"message": "Invalid document filepath"}, 400

            mapper_key = path_parts[3]

            documentmapper = redactionservice().getdocumentmapper(mapper_key)
            if not documentmapper:
                return {"message": "Document mapper not found"}, 404

            try:
                attributes = json.loads(documentmapper.get("attributes", "{}"))
            except json.JSONDecodeError:
                current_app.logger.error("Invalid document mapper attributes JSON")
                return {"message": "Invalid document mapper configuration"}, 500

            formsbucket = documentmapper.get("bucket")
            accesskey = attributes.get("s3accesskey")
            secretkey = attributes.get("s3secretkey")

            if not all([formsbucket, accesskey, secretkey]):
                return {"message": "S3 configuration incomplete"}, 500

            s3client = boto3.client(
                "s3",
                config=Config(signature_version="s3v4"),
                endpoint_url=f"https://{s3host}/",
                aws_access_key_id=accesskey,
                aws_secret_access_key=secretkey,
                region_name=s3region,
            )

            documentids = [
                d.get("file", {}).get("documentid")
                for d in documentobjs_input
                if d.get("file", {}).get("documentid")
            ]

            if not documentids:
                return {"message": "No valid document IDs provided"}, 400

            documents = documentservice().getdocumentbyids(documentids)
            if not documents:
                return {"message": "Documents not found"}, 404

            documentobjs_output = []

            for documentinfo in documentobjs_input:
                docid = documentinfo.get("file", {}).get("documentid")

                if not docid or docid not in documents:
                    current_app.logger.warning(
                        "Skipping document with missing metadata",
                        extra={"documentid": docid},
                    )
                    continue

                fullpath = documents.get(docid)
                if not fullpath:
                    current_app.logger.warning(
                        "Skipping document with empty filepath",
                        extra={"documentid": docid},
                    )
                    continue

                parts = fullpath.split("/")
                if len(parts) < 5:
                    current_app.logger.warning(
                        "Skipping document with invalid filepath",
                        extra={"documentid": docid, "filepath": fullpath},
                    )
                    continue

                object_key = "/".join(parts[4:])
                filename, file_extension = os.path.splitext(object_key)

                content_type = "{}/{}".format(
                    "image" if file_extension.lower() in imageextensions else "application",
                    file_extension.replace(".", ""),
                )

                try:
                    documentinfo["s3url"] = s3client.generate_presigned_url(
                        ClientMethod="get_object",
                        Params={
                            "Bucket": formsbucket,
                            "Key": object_key,
                            "ResponseContentType": content_type,
                        },
                        ExpiresIn=3600,
                        HttpMethod="GET",
                    )
                except Exception:
                    current_app.logger.exception(
                        "Failed to generate presigned URL",
                        extra={"documentid": docid},
                    )
                    documentinfo["s3url"] = None

                documentobjs_output.append(documentinfo)

            return json.dumps(documentobjs_output), 200

        except BusinessException as exception:
            current_app.logger.warning(
                "Business exception in presigned list",
                extra={"error": exception.message},
            )
            return {"message": exception.message}, exception.status_code

        except Exception:
            current_app.logger.exception("Unhandled error in presigned list")
            return {"message": "Failed to generate presigned URLs"}, 500


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
                    if "selectedfileprocessversion" in div["documentlist"][0] and div["documentlist"][0]["selectedfileprocessversion"] == 1:
                        document_s3_url = div["documentlist"][0]["filepath"]
                    elif "ocrfilepath" in div["documentlist"][0] and div["documentlist"][0]["ocrfilepath"] is not None:
                        document_s3_url = div["documentlist"][0]["ocrfilepath"]
                    elif "compressedfilepath" in div["documentlist"][0] and div["documentlist"][0]["compressedfilepath"] is not None:
                        document_s3_url = div["documentlist"][0]["compressedfilepath"]
                    else:
                        document_s3_url = div["documentlist"][0]["filepath"]
                    filepathlist = document_s3_url.split("/")[4:]
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
                        if "selectedfileprocessversion" in realfilepath and realfilepath["selectedfileprocessversion"] == 1:
                            document_s3_url = realfilepath["filepath"]
                        elif "ocrfilepath" in realfilepath and realfilepath["ocrfilepath"] is not None:
                            document_s3_url = realfilepath["ocrfilepath"]
                        elif "compressedfilepath" in realfilepath and realfilepath["compressedfilepath"] is not None:
                            document_s3_url = realfilepath["compressedfilepath"]
                        else:
                            document_s3_url = realfilepath["filepath"]
                        # filepathlist = doc["filepath"].split("/")[4:]
                        filepathlist = document_s3_url.split("/")[4:]
                        #print("filepathlist:",filepathlist)
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
                        if "selectedfileprocessversion" in div["documentlist"][0] and div["documentlist"][0]["selectedfileprocessversion"] == 1:
                            doc_s3_url = div["documentlist"][0]["filepath"]
                        elif "ocrfilepath" in div["documentlist"][0] and div["documentlist"][0]["ocrfilepath"] is not None:
                            doc_s3_url = div["documentlist"][0]["ocrfilepath"]
                        elif "compressedfilepath" in div["documentlist"][0] and div["documentlist"][0]["compressedfilepath"] is not None:
                            doc_s3_url = div["documentlist"][0]["compressedfilepath"]
                        else:
                            doc_s3_url = div["documentlist"][0]["filepath"]
                        filepathlist = doc_s3_url.split("/")[4:]
                        #filepathlist = div["documentlist"][0]["filepath"].split("/")[4:]
                        #print("filepathlist-is_single_redline:",filepathlist)
                        filename = filepathlist[0]
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
                            if ("selectedfileprocessversion" in doc and doc.get("selectedfileprocessversion")==1 and 
                                doc.get("filepath") not in filepaths):
                                filepaths.append(doc["filepath"])
                            elif "ocrfilepath" in doc and doc.get("ocrfilepath") not in filepaths:
                                filepaths.append(doc["filepath"])
                            elif "compressedfilepath" in doc and doc.get("compressedfilepath") not in filepaths:
                                filepaths.append(doc["compressedfilepath"])
                            elif doc.get("filepath") not in filepaths: 
                                    filepaths.append(doc["filepath"])
                            #if doc["filepath"] not in filepaths:
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
@API.route("/foiflow/oss/presigned/<int:ministryrequestid>/<redactionlayer>")
class FOIFlowS3PresignedResponsePackage(Resource):
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.ismemberofgroups(getrequiredmemberships())
    def post(ministryrequestid, redactionlayer="responsepackage"):
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
            elif redactionlayer == "openinfo":
                filename = "Response_Package_" + filename
                filepath_put = "{0}/{2}/{1}.pdf".format(
                    filepathlist[0], filename, redactionlayer
            )
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
@API.route('/foicrosstextsearch/authstring')
class FOISolr(Resource):
    """Get users"""

       
    @staticmethod
    @TRACER.trace()
    @cross_origin(origins=allowedorigins())
    @auth.require
    @auth.hasusertype('iao')
    def get():      
        try:                        
            usernamepassword ="%s:%s" % (os.getenv("FOI_SOLR_USERNAME"),os.getenv("FOI_SOLR_PASSWORD"))     
            print("usernamepassword:",usernamepassword)       
            unamepassword_bytes = usernamepassword.encode("utf-8")
            # Encode the bytes to Base64
            base64_encoded = base64.b64encode(unamepassword_bytes)
            return base64_encoded, 200
        except BusinessException as exception:            
            return {'status': exception.status_code, 'message':exception.message}, 500


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