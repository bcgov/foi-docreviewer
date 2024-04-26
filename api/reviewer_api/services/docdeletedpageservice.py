from reviewer_api.models.DocumentDeletedPages import DocumentDeletedPage
from reviewer_api.models.Documents import Document
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.PageCalculatorJob import PageCalculatorJob
from datetime import datetime
from reviewer_api.services.redactionlayerservice import redactionlayerservice
from reviewer_api.services.external.eventqueueproducerservice import eventqueueproducerservice
from os import getenv

pagecalculatorstreamkey = getenv("PAGECALCULATOR_STREAM_KEY")

class docdeletedpageservice:

    def newdeletepages(self, ministryid, docdeletedpage, userinfo):
        layerid = self.__getredactionlayerid(docdeletedpage["redactionlayer"])
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
        result = DocumentDeletedPage().create(ministryid, docpages, docpagecounts)
        if result.success:
                streamobject = {
                        'ministryrequestid': ministryid
                    }
                row = PageCalculatorJob(
                    version=1,
                    ministryrequestid=ministryid,
                    inputmessage=streamobject,
                    status='pushedtostream',
                    createdby='deletepages'
                )
                job = PageCalculatorJob.insert(row)
                streamobject["jobid"] = job.identifier
                streamobject["createdby"] = 'delete'
                eventqueueproducerservice().add(pagecalculatorstreamkey, streamobject)
        return result

    def getdeletedpages(self, ministryid):
        deletedmasterids = DocumentMaster.getdeleted(ministryid)
        activedocumentids = Document.getactivedocumentidsbyrequest(ministryid, deletedmasterids)
        deletedpages = DocumentDeletedPage().getdeletedpages(ministryid, activedocumentids)
        documentpages = {}
        if deletedpages: 
            for entry in deletedpages:
                if entry["documentid"] not in documentpages:
                    documentpages[entry["documentid"]] = entry["pagemetadata"]
                else:
                    pages = documentpages[entry["documentid"]]+entry["pagemetadata"]                
                    documentpages[entry["documentid"]] = list(set(pages))
        return documentpages
                

    def __getredactionlayerid(self, layername):
        return redactionlayerservice().getredactionlayerid(layername.lower())

