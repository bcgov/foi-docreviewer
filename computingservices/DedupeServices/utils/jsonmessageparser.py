import json
from models import dedupeproducermessage, s3credentials

def getdedupeproducermessage(producer_json):
    j = json.loads(producer_json)
    messageobject = dedupeproducermessage(**j)
    return messageobject

def gets3credentialsobject(s3cred_json):
    j = json.loads(s3cred_json)
    messageobject = s3credentials(**j)
    return messageobject    