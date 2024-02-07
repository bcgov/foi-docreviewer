
from marshmallow import EXCLUDE, fields, Schema
import json
from rstreamio.message.schemas.baseinfo import baseobj, dict2obj
"""
This class consolidates schemas of PageCount Calculation Service.

"""
class DocumentsPageCountIncomingSchema(Schema):

    jobid = fields.Int(data_key="jobid",allow_none=False)
    filename = fields.Str(data_key="filename",allow_none=True)
    pagecount = fields.Int(data_key="pagecount",allow_none=True)
    ministryrequestid = fields.Str(data_key="ministryrequestid",allow_none=False)
    documentmasterid = fields.Str(data_key="documentmasterid",allow_none=True)
    trigger = fields.Str(data_key="trigger",allow_none=True)
    createdby = fields.Str(data_key="createdby",allow_none=True)

def get_in_documents_pagecount_msg(producer_json):    
    messageobject = DocumentsPageCountIncomingSchema().load(__formatmsg(producer_json))
    return dict2obj(messageobject)

def __formatmsg(producer_json):
    j = json.loads(producer_json)
    return j  