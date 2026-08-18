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
        self.incompatible=bool(message.incompatible)
        self.usertoken=message.usertoken
        self.bcgovcode=message.bcgovcode
        self.attributes=message.attributes
        #self.needsocr = str(bool(message.needsocr)).lower() 
        if message.documentid is not None:
            self.documentid= int(message.documentid)
        if message.outputdocumentmasterid is not None:
            self.outputdocumentmasterid= int(message.outputdocumentmasterid)
        if message.originaldocumentmasterid is not None:
            self.originaldocumentmasterid=int(message.originaldocumentmasterid)

    def to_dict(self) -> dict[str, object]:
        payload = {
            "jobid": self.jobid,
            "s3filepath": self.s3filepath,
            "filename": self.filename,
            "ministryrequestid": self.ministryrequestid,
            "documentmasterid": self.documentmasterid,
            "trigger": self.trigger,
            "createdby": self.createdby,
            "requestnumber": self.requestnumber,
            "batch": self.batch,
            "incompatible": self.incompatible,
            "bcgovcode": self.bcgovcode,
            "attributes": self.attributes,
        }

        for field in (
            "documentid",
            "outputdocumentmasterid",
            "originaldocumentmasterid",
            "usertoken",
        ):
            value = getattr(self, field, None)
            if value is not None:
                payload[field] = value

        return payload
