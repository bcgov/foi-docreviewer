from reviewer_api.models.DocumentPageflags import DocumentPageflag
import json

class documentpageflagservice:

    
    def getpageflags(self, requestid):
        return DocumentPageflag.getpageflag_by_request(requestid)
    
    def getdocumentpageflags(self, requestid, documentid=None, version=None):
        pageflag  = DocumentPageflag.getpageflag(requestid, documentid, version)
        if pageflag not in (None, {}):
            return pageflag["pageflag"]
        return None

    
    def savepageflag(self, requestid, documentid, version, data, userinfo):
        pageflag = self.getdocumentpageflags(requestid, documentid, version)
        if pageflag is not None:
            isnew = True
            for entry in pageflag:
                if entry["page"] == data["page"]:
                    isnew = False
                    entry.update(data)
            if isnew == True:
                pageflag.append(data)
            return DocumentPageflag.updatepageflag(requestid, documentid, version, json.dumps(pageflag), json.dumps(userinfo))
        else:
            pageflag = []
            pageflag.append(data)
            return DocumentPageflag.createpageflag(requestid, documentid, version, json.dumps(pageflag), json.dumps(userinfo))

