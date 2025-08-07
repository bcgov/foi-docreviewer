from reviewer_api.models.DocumentPageflags import DocumentPageflag
import json
import copy
import logging
from reviewer_api.models.DocumentPageflags import DocumentPageflag
from reviewer_api.services.redactionlayerservice import redactionlayerservice
from reviewer_api.models.default_method_result import DefaultMethodResult
from datetime import datetime
from reviewer_api.services.docdeletedpageservice import docdeletedpageservice
from reviewer_api.utils.enums import RedactionPageFlagIDMapping

class documentpageflagservice:    
    def getpageflags_by_requestid_docids(self, requestid, redactionlayer, documentids):
        layerids = []

        if redactionlayerservice().isopeninfolayer(redactionlayer):
            layerids.append(redactionlayerservice().getdefaultredactionlayerid())
        else:
            layerids.append(redactionlayerservice().getredactionlayerid(redactionlayer))
            #layerids.append(redactionlayerservice().getdefaultredactionlayerid())       

        pageflags = DocumentPageflag.getpageflag_by_request_documentids(requestid, layerids, documentids)
        return self.__removedeletedpages(requestid, pageflags)
    
    def get_total_pages_by_ministryrequest_openinfo(self, ministryrequestids):
        layerid = 4  # openinfo layer id

        result = DocumentPageflag.get_pageflag_count_by_requestids(
            requestid=ministryrequestids,
            redactionlayerid=layerid
        )

        if not result:
            return None

        return result
    
    def getpublicbody(self, requestid, redactionlayer):
        redactionlayerid = redactionlayerservice().getredactionlayerid(redactionlayer)
        return DocumentPageflag.getpublicbody_by_request(requestid, redactionlayerid)

    def getdocumentpageflags(self, requestid, redactionlayerid, documentid=None, version=None):
        redactionlayer= redactionlayerservice().getredactionlayerbyid(redactionlayerid)
        layerids = redactionlayerservice().getmappedredactionlayers(redactionlayer)
        pageflag = DocumentPageflag.getpageflag(requestid, documentid, version, layerids)
        if pageflag not in (None, {}):
            return pageflag["pageflag"], pageflag["attributes"]
        return [], None

    def __removedeletedpages(self, requestid, pageflags):
        docdeletedpages = docdeletedpageservice().getdeletedpages(requestid)       
        for entry in pageflags:
            docid = entry["documentid"]
            deletedpages = docdeletedpages[docid] if docid in docdeletedpages else []
            entry["pageflag"] = self.__filterpages(entry["pageflag"], deletedpages)
        return pageflags
    
    def __filterpages(self, pageflag, deletedpages):
        return list(filter(lambda pgflag: pgflag['page'] not in deletedpages, pageflag))


    def getdocumentpageflagsbydocids(self, requestid, redactionlayerid, documentids):
        redactionlayer= redactionlayerservice().getredactionlayerbyid(redactionlayerid)
        layerids = redactionlayerservice().getmappedredactionlayers(redactionlayer)
        return DocumentPageflag.getpageflagsbydocids(requestid, documentids, layerids)

    def removebookmark(self, requestid, redactionlayerid, userinfo, documentids):
        pageflags = self.getdocumentpageflagsbydocids(requestid, redactionlayerid, documentids)
        for entry in pageflags:
            new_pageflag = list(filter(lambda x: x["flagid"] != 8, entry["pageflag"]))
            DocumentPageflag.savepageflag(
                requestid,
                entry["documentid"],
                entry["documentversion"],
                json.dumps(new_pageflag),
                json.dumps(userinfo),
                redactionlayerid,
            )
    def __getpageflags(self, requestid, redactionlayer):
        layerids = []
        layerids.append(redactionlayerservice().getredactionlayerid(redactionlayer))
        return DocumentPageflag.getpageflag_by_request_documentids(requestid, layerids)    

    def bulksavedocumentpageflag(self, requestid, documentid, version, pageflags, redactionlayerid, userinfo):
        redactionlayer= redactionlayerservice().getredactionlayerbyid(redactionlayerid)
        #Empty pageflag added to persist OI layer creation &
        #to tackle the layer count. OI Layer doesn't have any pageflags!!
        isopeninfolayer= redactionlayerservice().isopeninfolayer(redactionlayer['name'])       
        __docpageflags, __docpgattributes = [],None
        if isopeninfolayer == False:
            docpageflags, docpgattributes = self.getdocumentpageflags(requestid, redactionlayerid, documentid, version)
            for pageflag in pageflags:
                if self.__isbookmark(pageflag) == True:
                    self.removebookmark(requestid, redactionlayerid, userinfo, [documentid])
                docpgattributes = self.handlepublicbody(docpgattributes, pageflag)
                docpageflags = self.__createnewpageflag(docpageflags, pageflag)
            __docpgattributes = json.dumps(docpgattributes) if docpgattributes not in (None, "") else None
            __docpageflags = json.dumps(docpageflags) if docpageflags not in (None, "") else None
        return DocumentPageflag.savepageflag(requestid,documentid, version, __docpageflags, json.dumps(userinfo),redactionlayerid,__docpgattributes)

    async def bulkarchivedocumentpageflag(self, requestid, documentid, userinfo):
        return DocumentPageflag.bulkarchivepageflag(requestid,documentid,userinfo)

    def bulksavepageflag(self, requestid, data, userinfo):
        results = []
        for entry in data["documentpageflags"]:
            try:
                result = self.bulksavedocumentpageflag(requestid, entry["documentid"],entry["version"],entry["pageflags"],entry["redactionlayerid"],userinfo)
                results.append(
                    {
                        "documentid": entry["documentid"],
                        "version": entry["version"],
                        "redactionlayerid": entry["redactionlayerid"],
                        "message": result.message,
                        "updatedpageflag": result.identifier
                    }
                )
            except Exception as ex:
                logging.error(ex)
                results.append(
                    {
                        "documentid": entry["documentid"],
                        "version": entry["version"],
                        "redactionlayerid": entry["redactionlayerid"],
                        "message": "Page flag is not saved",
                    }
                )
        return results
    

    def handlepageflagattributes(self, docpgattributes, data):
        if "publicbodyaction" in data and data["publicbodyaction"] == "add":
            attributes = docpgattributes if docpgattributes not in (None, {}) else None
            publicbody = (
                attributes["publicbody"]
                if attributes not in (None, {}) and "publicbody" in attributes
                else []
            )
            print("handlepublicbody:")
            publicbody = set(map(lambda x: x["name"], publicbody))
            publicbody.update(data["other"])
            return {"publicbody": list(map(lambda x: {"name": x}, publicbody))}
        else:
            return docpgattributes

    # method to update pageflags by removing the necessary pageflags for a document
    def updatepageflags(self, requestid, deldocpagesmapping, redactionlayerid, userinfo):
        documentids = [
            item["docid"] for item in deldocpagesmapping if len(item["pages"]) > 0
        ]
        # get the pageflag details(all columns from table) for the pages with no redactions
        pageflags = self.getdocumentpageflagsbydocids(requestid, redactionlayerid, documentids)
        self.__filterandsavepageflags(
            pageflags, deldocpagesmapping, requestid, userinfo, redactionlayerid
        )

    def __filterandsavepageflags(self,pageflags,deldocpagesmapping,requestid,userinfo,redactionlayerid):
        for page_data in deldocpagesmapping:
            if len(page_data["pages"]) > 0:
                pages_to_remove = page_data["pages"]
                for pageflag in pageflags:
                    if pageflag["documentid"] == page_data["docid"]:
                        updatedpageflags = self.__getupdatedpageflag(pageflag, pages_to_remove)
                        pageflag["pageflag"] = (
                            json.dumps(updatedpageflags)
                            if updatedpageflags not in (None, "")
                            else None
                        )
                        break
                DocumentPageflag.savepageflag(requestid,pageflag["documentid"],pageflag["documentversion"],pageflag["pageflag"],json.dumps(userinfo),redactionlayerid,json.dumps(pageflag["attributes"]))

    def __getupdatedpageflag(self, pageflag, pages_to_remove):
        # returns the updated pageflag after removing the pages with pageflags [1, 3, 7]
        # conditions to check: if the page is part of pages_to_remove
        # or flagid in [1(Partial Disclosure), 3 (Withheld in Full), 7(In Progress)]
        return [entry for entry in pageflag["pageflag"] if entry["page"] not in pages_to_remove or entry["flagid"] not in [1, 2, 3, 7]]
    
    def __createnewpageflag(self, pageflag, data):
        formatted_data = self.__formatpageflag(data)  
        if not pageflag:
            pageflag = []
        match = [x for x in pageflag if x['page'] == data['page']] 
        filtered = [x for x in pageflag if x['page'] != data['page']]
        if len(match) == 0 and data['deleted'] == False:
            filtered.append(formatted_data)
        else:
            flag_consult = [x for x in match if x['flagid'] == 4]
            flag_nonconsults = [x for x in match if x['flagid'] != 4]
            flag_nonconsultsorphases = [x for x in match if x['flagid'] not in [4,9]]  
            flag_phase = [x for x in match if x['flagid'] == 9]
            flag_nonphase = [x for x in match if x['flagid'] != 9]
            if data['deleted'] == True:
                if data['flagid'] == 0:
                    if self.__isdeleteallowed(data['redactiontype'], flag_nonconsultsorphases) == True:
                        return filtered + flag_consult + flag_phase
                    else:
                        return filtered + flag_consult + flag_nonconsults
                elif data['flagid'] == 9:
                    return filtered + flag_nonphase
                return filtered + flag_nonconsults   
                #return filtered + flag_nonconsultsorphases            
            #Below block will only be executed during updates
            if data['flagid'] != 4 and len(flag_consult) > 0:
                filtered = filtered + flag_consult
            if data['flagid'] == 4 and len(flag_nonconsultsorphases) > 0:
                filtered = filtered + flag_nonconsultsorphases  
            if data['flagid'] != 9 and len(flag_phase) > 0:
                filtered = filtered + flag_phase
            if data['flagid'] == 9 and len(flag_nonconsultsorphases) > 0:
                filtered = filtered + flag_nonconsultsorphases


            filtered.append(formatted_data)
        return filtered
    
    def __isdeleteallowed(self, redactiontype, flag_nonconsults):      
        #Duplicate, Not Responsive
        if len(flag_nonconsults) > 0:
            existing_flag = flag_nonconsults[0]['flagid']
            if  existing_flag in (5,6):
                return False
            elif existing_flag == RedactionPageFlagIDMapping.get_flagid(redactiontype):  
                return True
        return False
        


    def __formatpageflag(self, data):
        _normalised = copy.deepcopy(data)
        if "publicbodyaction" in _normalised:
            del _normalised["publicbodyaction"]
        if "deleted" in data:
            del _normalised["deleted"]
        return _normalised

    def __isbookmark(self, data):
        if data["flagid"] == 8:
            return True
        return False
