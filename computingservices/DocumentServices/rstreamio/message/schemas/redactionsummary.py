
from marshmallow import EXCLUDE, fields, Schema
import json
from rstreamio.message.schemas.baseinfo import baseobj, dict2obj
from models.redactionsummary import redactionsummary
"""
This class consolidates schemas of RedactionSummary Service.

__author__   = "sumathi.thirumani@aot-technologies.com"

"""


class FileSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    filename = fields.Str(data_key="filename",allow_none=False)
    s3uripath = fields.Str(data_key="s3uripath",allow_none=False)

class SummaryPkgSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    divisionid = fields.Int(data_key="divisionid", allow_none=True)
    documentids = fields.List(fields.Int(), allow_none=True)

class SummarySchema(Schema):
    class Meta:
        unknown = EXCLUDE
    sorteddocuments = fields.List(fields.Int())
    pkgdocuments = fields.List(fields.Nested(SummaryPkgSchema, allow_none=True))
    
class AttributeSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    divisionid = fields.Int(data_key="divisionid",allow_none=True)
    files = fields.List(fields.Nested(FileSchema, allow_none=True))
    divisionname = fields.Str(data_key="divisionname",allow_none=True)

class RedactionSummaryIncomingSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    jobid = fields.Int(data_key="jobid",allow_none=False)
    requestid = fields.Int(data_key="requestid",allow_none=False)
    ministryrequestid = fields.Int(data_key="ministryrequestid",allow_none=False)
    category = fields.Str(data_key="category",allow_none=False)
    requestnumber = fields.Str(data_key="requestnumber",allow_none=False)
    bcgovcode = fields.Str(data_key="bcgovcode",allow_none=False)
    createdby = fields.Str(data_key="createdby",allow_none=False)
    filestozip = fields.List(fields.Nested(FileSchema, allow_none=True))
    finaloutput = fields.Str(data_key="finaloutput",allow_none=False)
    attributes = fields.List(fields.Nested(AttributeSchema, allow_none=True))
    summarydocuments = fields.Nested(SummarySchema, allow_none=True)
    redactionlayerid = fields.Int(data_key="redactionlayerid", allow_none=False)


def get_in_redactionsummary_msg(producer_json): 
    messageobject = RedactionSummaryIncomingSchema().load(__formatmsg(producer_json), unknown=EXCLUDE)
    return dict2obj(messageobject)

def __formatmsg(producer_json):
    j = json.loads(producer_json)
    return j

def decodesummarymsg(_message):
    _message = _message.encode().decode('unicode-escape')
    _message = _message.replace("b'","'").replace('"\'','"').replace('\'"','"')
    _message = _message.replace('"[','[').replace(']"',"]").replace("\\","")
    _message = _message.replace('"{','{').replace('}"',"}")
    _message = _message.replace('""','"')
    return _message