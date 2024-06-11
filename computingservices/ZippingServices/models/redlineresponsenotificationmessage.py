class redlineresponsenotificationmessage(object):
    def __init__(self, ministryrequestid, serviceid, errorflag, createdby,feeoverridereason) -> None:
        self.ministryrequestid = ministryrequestid
        self.serviceid = serviceid
        self.errorflag = errorflag
        self.createdby = createdby
        self.feeoverridereason=feeoverridereason
