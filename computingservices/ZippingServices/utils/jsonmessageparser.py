import json
from models import zipperproducermessage, s3credentials

def getzipperproducermessage(producer_json):
    j = json.loads(producer_json)
    messageobject = zipperproducermessage(**j)
    return messageobject

def gets3credentialsobject(s3cred_json):
    j = json.loads(s3cred_json)
    messageobject = s3credentials(**j)
    return messageobject    