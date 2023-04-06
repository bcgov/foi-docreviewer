
from marshmallow import EXCLUDE, fields

"""
This class  consolidates schemas of Notifications.

__author__      = "sumathi.thirumani@aot-technologies.com"

"""

class NotificationPublishSchema(object):
    ministryrequestid = fields.Int(data_key="ministryrequestid",allow_none=False) 
    serviceid = fields.Str(data_key="serviceid",allow_none=False)
    errorflag = fields.Str(data_key="errorflag",allow_none=False)
    createdby = fields.Str(data_key="message",allow_none=False)
    totalskippedfilecount = fields.Int(data_key="totalskippedfilecount",allow_none=True) 
    totalskippedfiles= fields.Str(data_key="totalskippedfiles",allow_none=True)