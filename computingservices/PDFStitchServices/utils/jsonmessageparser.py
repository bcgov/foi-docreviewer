import json
from models import s3credentials, pdfstitchproducermessage, pdfstitchfilesproducermessage

def getpdfstitchproducermessage(producer_json):
    j = json.loads(producer_json)
    messageobject = pdfstitchproducermessage(**j)
    return messageobject

def gets3credentialsobject(s3cred_json):
    j = json.loads(s3cred_json)
    messageobject = s3credentials(**j)
    return messageobject 

def getpdfstitchfilesproducermessage(producer_json):
    print("inside getpdfstitchfilesproducermessage")
    j = json.loads(producer_json)
    # print("J = ", j)
    messageobject = pdfstitchfilesproducermessage(**j)
    # print("messageobject = ", messageobject)
    return messageobject