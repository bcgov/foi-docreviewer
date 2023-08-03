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
            return pageflag["pageflag"], pageflag["attributes"]
        return [], None
    
    def removebookmark(self,requestid, userinfo):
        pageflags = self.getpageflags(requestid)
        for entry in pageflags:
            new_pageflag = list(filter(lambda x: x['flagid'] != 8 , entry['pageflag']))
            DocumentPageflag.savepageflag(requestid, entry['documentid'],  entry['documentversion'], json.dumps(new_pageflag), json.dumps(userinfo))
    
    def bulksavedocumentpageflag(self, requestid, documentid, version, pageflags, userinfo):
        docpageflags, docpgattributes = self.getdocumentpageflags(requestid, documentid, version)
        for pageflag in pageflags:
            if self.__isbookmark(pageflag) == True: 
                self.removebookmark(requestid, userinfo)
            docpgattributes = self.handlepublicbody(docpgattributes, pageflag)
            docpageflags = self.__createnewpageflag(docpageflags, pageflag)
        __docpgattributes = json.dumps({"publicbody": docpgattributes}) if docpgattributes not in (None, '') else None
        __docpageflags = json.dumps(docpageflags) if docpageflags not in (None, '') else None
        return DocumentPageflag.savepageflag(requestid, documentid, version, __docpageflags, json.dumps(userinfo),__docpgattributes)
        
    
    def bulksavepageflag(self, requestid, data, userinfo):
        results = []
        for entry in data["documentpageflags"]:
            try:
                result = self.bulksavedocumentpageflag(requestid, entry["documentid"], entry['version'], entry['pageflags'], userinfo)
                results.append({"documentid": entry["documentid"], "version": entry['version'], "message": result.message})
            except Exception as ex:
                logging.error(ex)
                results.append({"documentid": entry["documentid"], "version": entry['version'], "message": "Page flag is not saved"})
        return results  
        
    
    def handlepublicbody(self, docpgattributes, data):
        if "publicbodyaction" in data and data["publicbodyaction"] == "add":
            attributes = docpgattributes if docpgattributes not in (None,{}) else None
            publicbody = attributes["publicbody"] if attributes not in(None, {}) and "publicbody" in attributes else []
            publicbody = set(map(lambda x : x['name'], publicbody))
            publicbody.update(data["other"])
            return list(map(lambda x : {"name": x}, publicbody))
        else:
            return docpgattributes

    def removepageflag(self,requestid, documentid, version, page, userinfo):
        pageflags, _ = self.getdocumentpageflags(requestid, documentid, version)
        withheldinfullobj= next((obj for obj in pageflags if (obj["page"] == page and obj["flagid"] in [1, 3, 7]) ),None)
        if withheldinfullobj is not None:
            pageflags.remove(withheldinfullobj)
            DocumentPageflag.savepageflag(requestid, documentid, version, json.dumps(pageflags), json.dumps(userinfo))

    def __createnewpageflag(self, pageflag, data):
        formattted_data = self.__formatpageflag(data)
        if pageflag is not None and len(pageflag) > 0:
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
        return pageflag
    
    def __formatpageflag(self, data):
        _normalised = data
        if "publicbodyaction" in _normalised:
            del _normalised["publicbodyaction"]
        return _normalised    

    def __isbookmark(self, data):
        if data["flagid"] == 8:
            return True
        return False    

    
        

        
            


                    




