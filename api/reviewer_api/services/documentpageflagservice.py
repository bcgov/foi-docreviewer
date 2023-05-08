from reviewer_api.models.DocumentPageflags import DocumentPageflag
import json
import copy
import logging
from reviewer_api.models.DocumentPageflags import DocumentPageflag
from reviewer_api.models.default_method_result import DefaultMethodResult

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

    def removebookmark(self,requestid, userinfo):
        pageflags = self.getpageflags(requestid)
        for entry in pageflags:
            new_pageflag = list(filter(lambda x: x['flagid'] != 8 , entry['pageflag']))
            DocumentPageflag.updatepageflag(requestid, entry['documentid'],  entry['documentversion'], json.dumps(new_pageflag), json.dumps(userinfo))
    
    def savepageflag(self, requestid, documentid, version, data, userinfo):

        if self.__isbookmark(data) == True: 
            self.removebookmark(requestid, userinfo)
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
    

    def bulksavepageflags(self, requestid, documentid, version, pageflaglist, userinfo):
        pageflag = self.getdocumentpageflags(requestid, documentid, version)
        existingdocument = False
        for data in pageflaglist:
            existingdocument = False
            # if self.__isbookmark(data) == True: 
            #     self.removebookmark(requestid, userinfo)
            existingdocument= self.__createnewpageflag(pageflag,data)
        if existingdocument == True:
            result = DocumentPageflag.updatepageflag(requestid, documentid, version, json.dumps(pageflag), json.dumps(userinfo))
        else:
            result = DocumentPageflag.createpageflag(requestid, documentid, version, json.dumps(pageflag), json.dumps(userinfo))
            #self.handlepublicbody(requestid, documentid, version, data, userinfo)
        return result
        
    
    def removepageflag(self,requestid, documentid, version, page, userinfo):
        pageflags = self.getdocumentpageflags(requestid, documentid, version)
        withheldinfullobj= next((obj for obj in pageflags if (obj["page"] == page and obj["flagid"] in [1, 3]) ),None)
        if withheldinfullobj is not None:
            pageflags.remove(withheldinfullobj)
            DocumentPageflag.updatepageflag(requestid, documentid, version, json.dumps(pageflags), json.dumps(userinfo))

    def __createnewpageflag(self, pageflag,data):
        formattted_data = self.__formatpageflag(data)
        existingdocument = False
        if pageflag is not None:
            existingdocument = True
            isnew = True
            for entry in pageflag:
                if entry["page"] == data["page"]:
                    isnew = False
                    pageflag.remove(entry)
                    pageflag.append(formattted_data)
            if isnew == True:
                pageflag.append(formattted_data)
        else:
            pageflag = []
            pageflag.append(formattted_data)  
        return existingdocument
    
    def __formatpageflag(self, data):
        _normalised = copy.deepcopy(data)
        if "publicbodyaction" in _normalised:
            del _normalised["publicbodyaction"]
        return _normalised    

    def __isbookmark(self, data):
        if data["flagid"] == 8:
            return True
        return False    

    def handlepublicbody(self, requestid, documentid, version, data, userinfo):
        if "publicbodyaction" in data and data["publicbodyaction"] =="add":
            pageflag = DocumentPageflag.getpageflag(requestid, documentid, version)
            attributes = pageflag["attributes"] if pageflag["attributes"] not in (None,{}) else None
            publicbody = attributes["publicbody"] if attributes not in(None, {}) and "publicbody" in attributes else []
            publicbody = set(map(lambda x : x['name'], publicbody))
            publicbody.update(data["other"])
            publicbody = list(map(lambda x : {"name": x}, publicbody))
            DocumentPageflag.savepublicbody(requestid, documentid, version, json.dumps({"publicbody": publicbody}), json.dumps(userinfo))        
        else:
            return
        

        
            


                    




