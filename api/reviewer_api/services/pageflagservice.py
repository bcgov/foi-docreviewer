from reviewer_api.models.Pageflags import Pageflag
from reviewer_api.models.ProgramAreas import ProgramArea
from reviewer_api.services.documentpageflagservice import documentpageflagservice

import json

class pageflagservice:

    
    def getpageflags(self):
        pageflags = Pageflag.getall()
        programareas = ProgramArea.getprogramareas()
        for entry in pageflags:
            if entry["name"] == "Consult":
                entry["programareas"] = programareas
        return pageflags


    def getpageflag_by_request(self, requestid):
        pageflags = Pageflag.getall()
        programareas = ProgramArea.getprogramareas()  
        data = documentpageflagservice().getpublicbody(requestid)      
        for entry in pageflags:
            if entry["name"] == "Consult":
                entry["programareas"] = programareas
                if data not in (None, []):
                    entry["others"] = self.__getadditionlflags(data)
        return pageflags
    
    def __getadditionlflags(self, data):
        others = []
        for entry in data:
            _attributes = entry["attributes"]
            _publicbody = _attributes["publicbody"] if _attributes is not None and "publicbody" in _attributes else None
            if _publicbody is not None:
                for entry in _publicbody:
                    if entry["name"] not in others:
                        others.append(entry["name"])  
        return others  