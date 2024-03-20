from reviewer_api.models.DocumentPageflags import DocumentPageflag
import json
import copy
import logging
from reviewer_api.models.DocumentPageflags import DocumentPageflag
from reviewer_api.services.redactionlayerservice import redactionlayerservice
from reviewer_api.models.default_method_result import DefaultMethodResult
from datetime import datetime


class documentpageflagservice:    
    def getpageflags(self, requestid, redactionlayer, documentids):
        layerids = []
        layerids.append(redactionlayerservice().getredactionlayerid(redactionlayer))
        return DocumentPageflag.getpageflag_by_request(requestid, layerids, documentids)
    
    def getpublicbody(self, requestid, redactionlayer):
        redactionlayerid = redactionlayerservice().getredactionlayerid(redactionlayer)
        return DocumentPageflag.getpublicbody_by_request(requestid, redactionlayerid)

    def getdocumentpageflags(
        self, requestid, redactionlayerid, documentid=None, version=None
    ):
        layerids = redactionlayerservice().getmappedredactionlayers(
            {"redactionlayerid": redactionlayerid}
        )
        pageflag = DocumentPageflag.getpageflag(
            requestid, documentid, version, layerids
        )
        if pageflag not in (None, {}):
            return pageflag["pageflag"], pageflag["attributes"]
        return [], None

    def getdocumentpageflagsbydocids(self, requestid, redactionlayerid, documentids):
        layerids = redactionlayerservice().getmappedredactionlayers(
            {"redactionlayerid": redactionlayerid}
        )
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

    def bulksavedocumentpageflag(
        self, requestid, documentid, version, pageflags, redactionlayerid, userinfo
    ):
        docpageflags, docpgattributes = self.getdocumentpageflags(
            requestid, redactionlayerid, documentid, version
        )
        for pageflag in pageflags:
            if self.__isbookmark(pageflag) == True:
                self.removebookmark(requestid, redactionlayerid, userinfo, [documentid])
            docpgattributes = self.handlepublicbody(docpgattributes, pageflag)
            docpageflags = self.__createnewpageflag(docpageflags, pageflag)
        __docpgattributes = (
            json.dumps(docpgattributes) if docpgattributes not in (None, "") else None
        )
        __docpageflags = (
            json.dumps(docpageflags) if docpageflags not in (None, "") else None
        )
        return DocumentPageflag.savepageflag(
            requestid,
            documentid,
            version,
            __docpageflags,
            json.dumps(userinfo),
            redactionlayerid,
            __docpgattributes,
        )

    async def bulkarchivedocumentpageflag(
        self, requestid, documentid, userinfo
    ):
        return DocumentPageflag.bulkarchivepageflag(
            requestid,
            documentid,
            userinfo
        )

    def bulksavepageflag(self, requestid, data, userinfo):
        results = []
        for entry in data["documentpageflags"]:
            try:
                result = self.bulksavedocumentpageflag(
                    requestid,
                    entry["documentid"],
                    entry["version"],
                    entry["pageflags"],
                    entry["redactionlayerid"],
                    userinfo,
                )
                results.append(
                    {
                        "documentid": entry["documentid"],
                        "version": entry["version"],
                        "redactionlayerid": entry["redactionlayerid"],
                        "message": result.message,
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

    def handlepublicbody(self, docpgattributes, data):
        if "publicbodyaction" in data and data["publicbodyaction"] == "add":
            attributes = docpgattributes if docpgattributes not in (None, {}) else None
            publicbody = (
                attributes["publicbody"]
                if attributes not in (None, {}) and "publicbody" in attributes
                else []
            )
            publicbody = set(map(lambda x: x["name"], publicbody))
            publicbody.update(data["other"])
            return {"publicbody": list(map(lambda x: {"name": x}, publicbody))}
        else:
            return docpgattributes

    def removepageflag(
        self, requestid, documentid, version, page, redactionlayerid, userinfo
    ):
        pageflags, _ = self.getdocumentpageflags(
            requestid, redactionlayerid, documentid, version
        )
        withheldinfullobj = next(
            (
                obj
                for obj in pageflags
                if (obj["page"] == page and obj["flagid"] in [1, 3, 7])
            ),
            None,
        )
        if withheldinfullobj is not None:
            pageflags.remove(withheldinfullobj)
            DocumentPageflag.savepageflag(
                requestid,
                documentid,
                version,
                json.dumps(pageflags),
                json.dumps(userinfo),
                redactionlayerid,
            )

    # method to update pageflags by removing the necessary pageflags for a document
    def updatepageflags(
        self, requestid, deldocpagesmapping, redactionlayerid, userinfo
    ):
        documentids = [
            item["docid"] for item in deldocpagesmapping if len(item["pages"]) > 0
        ]
        # get the pageflag details(all columns from table) for the pages with no redactions
        pageflags = self.getdocumentpageflagsbydocids(
            requestid, redactionlayerid, documentids
        )
        self.__filterandsavepageflags(
            pageflags, deldocpagesmapping, requestid, userinfo, redactionlayerid
        )

    def bulkupdatepageflags(self, requestid, data, redactionlayerid, userinfo):
        docids = [docflagobj["docid"] for docflagobj in data]
        previousdocpageflags = self.getdocumentpageflagsbydocids(requestid, redactionlayerid, docids)
        # loop through data and adjust docobj in data (updated page flags to apply to page / doc id) with previous docpageflag data (data from DocumentPageFlag Table)
        for docflagobj in data:
            for prevdocflagobj in previousdocpageflags:
                if (docflagobj['docid'] == prevdocflagobj['documentid']):
                    docflagobj['version'] = prevdocflagobj['documentversion']
                    docflagobj["attributes"] = prevdocflagobj["attributes"]
                    docflagobj['pageflag'] = self.__findandreplacepageflags(docflagobj['pageflag'], prevdocflagobj['pageflag'])
            DocumentPageflag.savepageflag(
                requestid,
                docflagobj["docid"],
                docflagobj["version"],
                json.dumps(docflagobj['pageflag']),
                json.dumps(userinfo),
                redactionlayerid,
                json.dumps(docflagobj["attributes"]),
            )

    def __filterandsavepageflags(
        self,
        pageflags,
        deldocpagesmapping,
        requestid,
        userinfo,
        redactionlayerid,
    ):
        for page_data in deldocpagesmapping:
            if len(page_data["pages"]) > 0:
                pages_to_remove = page_data["pages"]
                for pageflag in pageflags:
                    if pageflag["documentid"] == page_data["docid"]:
                        updatedpageflags = self.__getupdatedpageflag(
                            pageflag, pages_to_remove
                        )
                        pageflag["pageflag"] = (
                            json.dumps(updatedpageflags)
                            if updatedpageflags not in (None, "")
                            else None
                        )
                        break
                DocumentPageflag.savepageflag(
                    requestid,
                    pageflag["documentid"],
                    pageflag["documentversion"],
                    pageflag["pageflag"],
                    json.dumps(userinfo),
                    redactionlayerid,
                    json.dumps(pageflag["attributes"]),
                )

    def __getupdatedpageflag(self, pageflag, pages_to_remove):
        # returns the updated pageflag after removing the pages with pageflags [1, 3, 7]
        # conditions to check: if the page is part of pages_to_remove
        # or flagid in [1(Partial Disclosure), 3 (Withheld in Full), 7(In Progress)]
        return [
            entry
            for entry in pageflag["pageflag"]
            if entry["page"] not in pages_to_remove or entry["flagid"] not in [1, 3, 7]
        ]

    def __createnewpageflag(self, pageflag, data):
        formatted_data = self.__formatpageflag(data)        
        if not pageflag:
            pageflag = []
        isnew = True
        updated = False
        for index, entry in enumerate(pageflag):
            if entry["page"] == data["page"]:
                isnew = False
                if data["flagid"] == 4:
                    pageflag, updated = self.__handleconsultflag(data, entry, index, pageflag, formatted_data, updated)
                # handle all other flags except consult
                elif data["flagid"] != 4 and entry["flagid"] != 4:
                    del pageflag[index]
                    pageflag.append(formatted_data)
                    updated = True
                    break

        if isnew or not updated:
            pageflag.append(formatted_data)

        return pageflag
    
    def __handleconsultflag(self, data, entry, index, pageflag, formatted_data, updated):
        # remove consult flag
        if data["flagid"] == 4 and not data["other"] and not data["programareaid"]:
            if entry["flagid"] == data["flagid"]:
                del pageflag[index]
                updated = True
                return pageflag, updated
        # update consult flag
        elif data["flagid"] == 4 and entry["flagid"] == data["flagid"]:
            del pageflag[index]
            pageflag.append(formatted_data)
            updated = True
            return pageflag, updated
        return pageflag, updated

    def __formatpageflag(self, data):
        _normalised = data
        if "publicbodyaction" in _normalised:
            del _normalised["publicbodyaction"]
        return _normalised

    def __isbookmark(self, data):
        if data["flagid"] == 8:
            return True
        return False

    def __findandreplacepageflags(self, newpageflags, previouspageflags):
        updatedpageflags = []
        dictlookup =  {item["page"]: item["flagid"] for item in newpageflags}
        for pageflag in previouspageflags:
            page = pageflag['page']
            if page in dictlookup:
                updatedpageflags.append({
                    "page": page,
                    "flagid": dictlookup.get(page)
                })
            else:
                updatedpageflags.append(pageflag)
        return [pageflag for pageflag in updatedpageflags if pageflag['flagid'] is not None]