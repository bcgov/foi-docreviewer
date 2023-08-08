
class harmsnotificationmessage(object):

    def __init__(self,ministryrequestid,serviceid,errorflag,createdby,totalskippedfilecount,totalskippedfiles) -> None:
        self.ministryrequestid = ministryrequestid 
        self.serviceid = serviceid
        self.errorflag = errorflag
        self.createdby = createdby
        self.totalskippedfilecount = totalskippedfilecount
        self.totalskippedfiles= totalskippedfiles