import json

class compressionproducermessage(object):
    def __init__(self,jobid,message) -> None:
        self.jobid = jobid
        self.s3filepath = message.s3filepath
        self.filename = message.filename
        self.ministryrequestid = int(message.ministryrequestid)        
        self.documentmasterid = int(message.documentmasterid)
        self.trigger = message.trigger
        self.createdby = message.createdby
        self.requestnumber = message.requestnumber
        self.batch=message.batch
        self.incompatible=str(bool(message.incompatible)).lower() 
        self.usertoken=message.usertoken
        self.bcgovcode=message.bcgovcode
        self.attributes= json.dumps(message.attributes)
        self.needsocr = str(bool(message.needsocr)).lower() 
        if message.documentid is not None:
            self.documentid= int(message.documentid)
        if message.outputdocumentmasterid is not None:
            self.outputdocumentmasterid= int(message.outputdocumentmasterid)
        if message.originaldocumentmasterid is not None:
            self.originaldocumentmasterid=int(message.originaldocumentmasterid)