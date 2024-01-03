from reviewer_api.models.Sections import Section
from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.services.redactionlayerservice import redactionlayerservice
import json

class sectionservice:

    
    def getsections(self):
        return Section.getall()
    
    def getsections_by_ministryid(self, ministryid, redactionlayer):
        globalsections = self.getsections()
        redactionlayerid = redactionlayerservice().getredactionlayerid(redactionlayer)
        annotationsections = annotationservice().getannotationsections(ministryid, redactionlayerid)        
        requestsections = []
        for annotationsection in annotationsections:
            _annotationsection = json.loads(json.dumps(annotationsection["section"])) 
            _section = json.loads(_annotationsection)
            for entry in _section["ids"]:
                requestsections = self.__updateoccurance(globalsections, requestsections, entry)  
        return self.__mergesections(globalsections, requestsections)
    
    
    def __mergesections(self, globalsections, requestsections):
        _sortedrequestsections = self.__sortbyoccurance(requestsections)
        for section in globalsections:
            if self.__getoccurancecount(_sortedrequestsections, section["sectionid"]) == 1:
                _sortedrequestsections.append({"id":section["sectionid"], "section":section["section"], "description": section["description"], "count":0})
        index = 1
        for section in _sortedrequestsections:
            section["sortorder"] = index
            index = index+1
        return _sortedrequestsections

    def __sortbyoccurance(self, requestsections):
        if requestsections not in (None,[]):
            return sorted(requestsections, key=lambda k: int(k['count']), reverse = True)
        return requestsections
    
    
    def __updateoccurance(self, globalsections, requestsections, entry):
        _count = self.__getoccurancecount(requestsections, entry["id"])
        if _count > 1 :
            for _requestsection in requestsections:
                if _requestsection["id"] ==  entry["id"]:
                    _requestsection["count"] = _count            
        else:
            entry["count"] = _count
            entry["description"] = self.__getdescription(globalsections, entry["id"])
            requestsections.append(entry)   
        return requestsections 

    def __getdescription(self, globalsections, sectionid):
        for globalsection in globalsections:
            if globalsection["sectionid"] == sectionid:
                return globalsection["description"]
        return None

    def __getoccurancecount(self, sections, sectionid):
        count = 1
        for section in sections:
            if int(section["id"]) == int(sectionid):
                count = section["count"] + 1
        return count