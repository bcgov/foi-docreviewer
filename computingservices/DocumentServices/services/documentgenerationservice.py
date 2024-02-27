#from reviewer_api.services.cdogs_api_service import cdogsapiservice
from services.dal.documenttemplate import documenttemplate
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
        

    def generate_pdf(self, data, documenttypename='redline_redaction_summary', template_path='templates/redline_redaction_summary.docx'):
        access_token= cdogsapiservice()._get_access_token()
        template_cached = False
        templatefromdb= self.__gettemplate(documenttypename)
        if templatefromdb is not None and templatefromdb["cdogs_hash_code"] is not None:
            template_cached = cdogsapiservice().check_template_cached(templatefromdb["cdogs_hash_code"], access_token)
            templatecdogshashcode = templatefromdb["cdogs_hash_code"]
            print("template_cached:",template_cached)
            
        if templatefromdb is None or templatefromdb["cdogs_hash_code"] is None or not template_cached:
            templatecdogshashcode = cdogsapiservice().upload_template(template_path, access_token)
            print("templatecdogshashcode:",templatecdogshashcode)
            if templatefromdb is not None and templatefromdb["document_type_id"] is not None:
                templatefromdb["cdogs_hash_code"] = templatecdogshashcode
                documenttemplate().updatecdogshashcode(templatefromdb["document_type_id"], templatefromdb["cdogs_hash_code"])
        return cdogsapiservice().generate_pdf(templatecdogshashcode, data,access_token)
    
    def __gettemplate(self,documenttypename='redline_redaction_summary'):
        try:
            templatefromdb=None
            summary_cdogs_hash_code=None
            summary_document_type_id =documenttemplate().getdocumenttypebyname(documenttypename)
            print("summary_document_type_id:",summary_document_type_id)
            if summary_document_type_id is not None:             
                summary_cdogs_hash_code=documenttemplate().gettemplatebytype(summary_document_type_id)
                templatefromdb = {"document_type_id": summary_document_type_id, "cdogs_hash_code":summary_cdogs_hash_code}
                print("templatefromdb:",templatefromdb)
            return templatefromdb
        except (Exception) as error:
            print('error occured in document generation service - gettemplate method: ', error)

