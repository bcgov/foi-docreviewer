
from marshmallow import EXCLUDE, fields, Schema
import json
from rstreamio.message.schemas.baseinfo import baseobj, dict2obj
from models.redactionsummary import redactionsummary
"""
This class consolidates schemas of RedactionSummary Service.

__author__   = "sumathi.thirumani@aot-technologies.com"

"""
class RedactionSummaryIncomingSchema(Schema):
    jobid = fields.Int(data_key="jobid",allow_none=False)
    requestid = fields.Int(data_key="requestid",allow_none=False)
    ministryrequestid = fields.Int(data_key="ministryrequestid",allow_none=False)
    category = fields.Str(data_key="category",allow_none=False)
    requestnumber = fields.Str(data_key="requestnumber",allow_none=False)
    bcgovcode = fields.Str(data_key="bcgovcode",allow_none=False)
    createdby = fields.Str(data_key="createdby",allow_none=False)
    filestozip = fields.Str(data_key="filestozip",allow_none=False)
    finaloutput = fields.Str(data_key="finaloutput",allow_none=False)
    attributes =  fields.Str(data_key="attributes",allow_none=False)
    summarydocuments = fields.Str(data_key="summarydocuments",allow_none=False)
    redactionlayerid = fields.Int(data_key="redactionlayerid", allow_none=False)

def get_in_redactionsummary_msg(producer_json):    
    messageobject = RedactionSummaryIncomingSchema().load(__formatmsg(producer_json))
    return dict2obj(messageobject)

def getzipperproducermessage(producer_json):
    j = json.loads(producer_json)
    messageobject = redactionsummary(**j)
    return messageobject


def __formatmsg(producer_json):
    j = json.loads(producer_json)
    return j  