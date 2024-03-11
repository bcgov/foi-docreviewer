from reviewer_api.models.DocumentDeletedPages import DocumentDeletedPage
from reviewer_api.models.Documents import Document
from datetime import datetime
from reviewer_api.services.redactionlayerservice import redactionlayerservice

class docdeletedpageservice:

    def deletepages(self, ministryid, redactionlayer, docdeletedpage, userinfo):
        layerid = self.__getredactionlayerid(redactionlayer)
        docs = Document.getdocumentpagedatabyrequest(ministryid)
        docpages = []
        docpagecounts= []
        for entry in docdeletedpage["documentpages"]:
            docid = entry["docid"]
            docpages.append({
                    "redactionlayerid": layerid,
                    "ministryrequestid": ministryid,  
                    "documentid": docid,                  
                    "pagemetadata": entry["pages"],
                    "createdby": userinfo                    
                    })
            docpagecounts.append({
                "documentid": docid, 
                "foiministryrequestid": ministryid, 
                "version":1, 
                "pagecount": docs[docid]-len(entry["pages"]),
                "updatedby": userinfo,
                "updated_at": datetime.now()
                })
        return DocumentDeletedPage().create(ministryid, docpages, docpagecounts)

    def getdeletedpages(self, ministryid):
        deletedpages = DocumentDeletedPage().getdeletedpages(ministryid)
        documentpages = {}
        for entry in deletedpages:
            if entry["documentid"] not in documentpages:
                documentpages[entry["documentid"]] = entry["pagemetadata"]
            else:
                documentpages[entry["documentid"]] = documentpages[entry["documentid"]]+entry["pagemetadata"]
        return documentpages
                

    def __getredactionlayerid(self, layername):
        return redactionlayerservice().getredactionlayerid(layername)

