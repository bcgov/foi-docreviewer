
from marshmallow import EXCLUDE, fields, Schema
import json
from rstreamio.message.schemas.baseinfo import baseobj, dict2obj
from models.redactionsummary import redactionsummary
"""
This class consolidates schemas of RedactionSummary Service.

__author__   = "sumathi.thirumani@aot-technologies.com"

"""


class FileSchema(Schema):
    def __init__(self, filename, s3uripath) -> None:
        self.filename = filename
        self.s3uripath = s3uripath

class SummaryPackage(Schema):
    def __init__(self, divisionid, documentids) -> None:
        self.divisionid = divisionid
        self.documentids = documentids

class Summary(Schema):
    def __init__(self, sorteddocuments, pkgdocuments) -> None:
        self.sorteddocuments = sorteddocuments
        self.pkgdocuments = pkgdocuments



class RedactionSummaryMessage(object):
    def __init__(self, jobid, requestid, ministryrequestid, category, requestnumber, 
                 bcgovcode, createdby, filestozip, finaloutput, attributes, summarydocuments ,redactionlayerid) -> None:
        self.jobid = jobid
        self.requestid = requestid
        self.ministryrequestid = ministryrequestid
        self.category = category
        self.requestnumber = requestnumber
        self.bcgovcode = bcgovcode
        self.createdby = createdby
        self.filestozip = filestozip
        self.finaloutput = finaloutput
        self.attributes = attributes
        self.summarydocuments = summarydocuments
        self.redactionlayerid = redactionlayerid


def get_in_redactionsummary_msg(producer_json): 
    messageobject = RedactionSummaryMessage(**__formatmsg(producer_json))
    return messageobject

def get_in_summary_object(producer_json): 
    messageobject = Summary(**__formatmsg(producer_json))
    return messageobject

def get_in_summarypackage_object(producer_json): 
    messageobject = SummaryPackage(**__formatmsg(producer_json))
    return messageobject

def __formatmsg(producer_json):
    j = json.loads(producer_json)
    return j

