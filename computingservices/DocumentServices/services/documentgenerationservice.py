#from reviewer_api.services.cdogs_api_service import cdogsapiservice
from services.dal.documenttemplateservice import documenttemplateservice
from services.dal.documenttypeservice import documenttypeservice
from .cdogsapiservice import cdogsapiservice
import json
import logging
from aws_requests_auth.aws_auth import AWSRequestsAuth
import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
import requests
import mimetypes



s3host = os.getenv("OSS_S3_HOST")
s3region = os.getenv("OSS_S3_REGION")

class documentgenerationservice:
    """document generation Service class."""

    # def __init__(self,documenttypename='redaction_summary'):
    #     self.cdgos_api_service = cdogsapiservice()
    #     self.documenttypename = documenttypename
    #     receipt_document_type : DocumentType = DocumentType.get_document_type_by_name(self.documenttypename)
    #     if receipt_document_type is None:
    #         raise BusinessException(Error.DATA_NOT_FOUND)
        
    #     self.receipt_template : DocumentTemplate = DocumentTemplate \
    #         .get_template_by_type(document_type_id = receipt_document_type.document_type_id)
    #     if self.receipt_template is None:
    #         raise BusinessException(Error.DATA_NOT_FOUND)  
        

    def generate_pdf(self, documenttypename, data, receipt_template_path='templates/redline_redaction_summary.docx'):
        access_token= cdogsapiservice()._get_access_token()
        template_cached = False
        templatefromdb= self.__gettemplate(documenttypename)
        print("\n***templatefromdb:",templatefromdb)
        if templatefromdb is not None and templatefromdb["cdogs_hash_code"]:
            print('Checking if template %s is cached', templatefromdb["cdogs_hash_code"])
            template_cached = cdogsapiservice().check_template_cached(templatefromdb["cdogs_hash_code"], access_token)
            templatecdogshashcode = templatefromdb["cdogs_hash_code"]
            
        if templatefromdb is None or templatefromdb["cdogs_hash_code"] is None or not template_cached:
            templatecdogshashcode = cdogsapiservice().upload_template(receipt_template_path, access_token)
            print('Uploading new template--->',templatecdogshashcode)
            if templatefromdb is not None:
                documenttemplateservice().updatecdogshashcode(templatefromdb["document_type_id"], templatefromdb["cdogs_hash_code"])
            # receipt_template.flush()
            # receipt_template.commit()
        print('Generating redaction summary')
        return cdogsapiservice().generate_pdf(templatecdogshashcode, data,access_token)
    
    def __gettemplate(self,documenttypename='redline_redaction_summary'):
        try:
            receipt_document_type =documenttypeservice().getdocumenttypebyname(documenttypename)
            receipt_template=None
            if receipt_document_type is not None:                          
                receipt_template=documenttemplateservice().gettemplatebytype(receipt_document_type.document_type_id)
            return receipt_template
        except (Exception) as error:
            print('error occured in document generation service - gettemplate method: ', error)

    # def upload_receipt(self, filename, filebytes, ministryrequestid, ministrycode, filenumber):
    #     try:
    #         logging.info("Upload summary for ministry request id"+ str(ministryrequestid))
    #         _response =  self.__uploadbytes(filename, filebytes, ministrycode, filenumber)
    #         logging.info("Upload status for payload"+ json.dumps(_response))
    #         if _response["success"] == True:
    #             _documentschema = {"documents": [{"filename": _response["filename"], "documentpath": _response["documentpath"]}]}
    #         return _response
    #     except Exception as ex:
    #         logging.exception(ex)
