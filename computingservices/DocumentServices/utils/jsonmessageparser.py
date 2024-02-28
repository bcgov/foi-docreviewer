import json
from models import s3credentials

def gets3credentialsobject(s3cred_json):
    j = json.loads(s3cred_json)
    messageobject = s3credentials(**j)
    return messageobject 
