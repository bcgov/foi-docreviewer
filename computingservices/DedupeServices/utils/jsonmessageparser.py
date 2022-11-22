import json
from models import dedupeproducermessage

def getdedupeproducermessage(producer_json):
    j = json.loads(producer_json)
    messageobject = dedupeproducermessage(**j)
    return messageobject