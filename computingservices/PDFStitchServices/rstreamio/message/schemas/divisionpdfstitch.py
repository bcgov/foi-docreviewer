
from marshmallow import EXCLUDE, fields, Schema
import json
from rstreamio.message.schemas.baseinfo import baseobj, dict2obj
"""
This class  consolidates schemas of Notifications.

__author__      = "sumathi.thirumani@aot-technologies.com"

"""

class FileSchema(Schema):
    filename = fields.Str(data_key="filename",allow_none=False)
    s3filepath = fields.Str(data_key="s3filepath",allow_none=False)

class AttributeSchema(Schema):
    division = fields.Str(data_key="division",allow_none=False)
    files = fields.List(fields.Nested(FileSchema, allow_none=True))

class DivisionPdfStitchMsgSchema(Schema, baseobj):
    requestnumber = fields.Str(data_key="requestnumber",allow_none=False)
    bcgovcode = fields.Str(data_key="bcgovcode",allow_none=False)
    attributes = fields.List(fields.Nested(AttributeSchema, allow_none=True))

def get_in_divisionpdfmsg(producer_json):    
    print("inside get_in_divisionpdfmsg")
    #print(producer_json)
    messageobject = DivisionPdfStitchMsgSchema().load(__formatmsg(producer_json))
    return dict2obj(messageobject)

def __formatmsg(producer_json):
    j = json.loads(producer_json)
    if "attributes" in j:
        attributes = j["attributes"]
        del j["attributes"]
        j["attributes"] = json.loads(attributes)
    return j  