class pagecalculatorproducermessage(object):
    def __init__(self,s3filepath,filename,ministryrequestid,documentmasterid,trigger,outputdocumentmasterid=None,originaldocumentmasterid=None) -> None:
        self.s3filepath = s3filepath        
        self.filename=filename
        self.ministryrequestid=ministryrequestid        
        self.documentmasterid=documentmasterid
        # self.outputdocumentmasterid=outputdocumentmasterid
        # self.originaldocumentmasterid=originaldocumentmasterid
        self.trigger=trigger
        