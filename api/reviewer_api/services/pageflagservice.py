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
        for entry in pageflags:
            if entry["name"] == "Consult":
                entry["programareas"] = programareas
                entry["others"] = self.__getadditionlflags(requestid)
        return pageflags
    
    def __getadditionlflags(self, requestid):
        others = []
        data = documentpageflagservice().getpageflags(requestid)
        consultid = Pageflag.getpageid("Consult")
        if data not in (None, []):
            for entry in data:
                for pageflag in entry["pageflag"]:
                    if pageflag["flagid"] == consultid and "other" in pageflag:
                        if pageflag["other"] not in others:
                            others.append(pageflag["other"])  
        return others  