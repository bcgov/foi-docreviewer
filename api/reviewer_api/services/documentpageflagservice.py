from reviewer_api.models.DocumentPageflags import DocumentPageflag
import json
import copy

class documentpageflagservice:

    
    def getpageflags(self, requestid):
        return DocumentPageflag.getpageflag_by_request(requestid)
    
    def getpublicbody(self, requestid):
        return DocumentPageflag.getpublicbody_by_request(requestid)
    
    def getdocumentpageflags(self, requestid, documentid=None, version=None):
        pageflag  = DocumentPageflag.getpageflag(requestid, documentid, version)
        if pageflag not in (None, {}):
            return pageflag["pageflag"]
        return None

    
    def savepageflag(self, requestid, documentid, version, data, userinfo):
        pageflag = self.getdocumentpageflags(requestid, documentid, version)
        formattted_data = self.__formatpageflag(data)
        if pageflag is not None:
            isnew = True
            for entry in pageflag:
                if entry["page"] == data["page"]:
                    isnew = False
                    pageflag.remove(entry)
                    pageflag.append(formattted_data)
            if isnew == True:
                pageflag.append(formattted_data)
            result = DocumentPageflag.updatepageflag(requestid, documentid, version, json.dumps(pageflag), json.dumps(userinfo))
        else:
            pageflag = []
            pageflag.append(formattted_data)
            result = DocumentPageflag.createpageflag(requestid, documentid, version, json.dumps(pageflag), json.dumps(userinfo))
        self.handlepublicbody(requestid, documentid, version, data, userinfo)
        return result
    
    def __formatpageflag(self, data):
        _normalised = copy.deepcopy(data)
        if "publicbodyaction" in _normalised:
            del _normalised["publicbodyaction"]
        return _normalised    

    def handlepublicbody(self, requestid, documentid, version, data, userinfo):
        if "publicbodyaction" in data and data["publicbodyaction"] =="add":
            pageflag = DocumentPageflag.getpageflag(requestid, documentid, version)
            attributes = pageflag["attributes"] if pageflag["attributes"] not in (None,{}) else None
            publicbody = attributes["publicbody"] if attributes not in(None, {}) and "publicbody" in attributes else []
            publicbody.append({"name": data["other"]})    
            DocumentPageflag.savepublicbody(requestid, documentid, version, json.dumps({"publicbody": publicbody}), json.dumps(userinfo))        
        else:
            return
        

        
            


                    




