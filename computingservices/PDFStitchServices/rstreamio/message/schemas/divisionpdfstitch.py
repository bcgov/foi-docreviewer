
from marshmallow import EXCLUDE, fields, Schema
import json
from rstreamio.message.schemas.baseinfo import baseobj, dict2obj
"""
This class  consolidates schemas of Notifications.

__author__      = "sumathi.thirumani@aot-technologies.com"

"""

class FileSchema(Schema):

    recordid = fields.Int(data_key="recordid",allow_none=True)
    filename = fields.Str(data_key="filename",allow_none=False)
    s3uripath = fields.Str(data_key="s3uripath",allow_none=False)
    lastmodified = fields.Str(data_key="lastmodified",allow_none=False)

class AttributeSchema(Schema):

    files = fields.Nested(FileSchema, many=True,allow_none=False)
    divisionname = fields.Str(data_key="divisionname",allow_none=False)
    divisionid = fields.Int(data_key="divisionid", allow_none=False)

class DivisionPdfStitchMsgSchema(Schema, baseobj):

    jobid = fields.Int(data_key="jobid", allow_none=False)
    category = fields.Str(data_key="category",allow_none=False)
    requestnumber = fields.Str(data_key="requestnumber",allow_none=False)
    bcgovcode = fields.Str(data_key="bcgovcode",allow_none=False)
    attributes = fields.Nested(AttributeSchema, many=True, required=True,allow_none=False)
    requestid = fields.Str(data_key="requestid",allow_none=False)
    ministryrequestid = fields.Str(data_key="ministryrequestid",allow_none=False)
    createdby = fields.Str(data_key="createdby",allow_none=False)

def get_in_divisionpdfmsg(producer_json):
    messageobject = DivisionPdfStitchMsgSchema().load(__formatmsg(producer_json))
    return dict2obj(messageobject)

def get_in_filepdfmsg(producer_json):
    messageobject = FileSchema().load(__formatmsg(producer_json))
    return dict2obj(messageobject)

def __formatmsg(producer_json):
    j = json.loads(producer_json)
    if "attributes" in j:
        attributes = j["attributes"]
        del j["attributes"]
        j["attributes"] = json.loads(attributes)
    return j  