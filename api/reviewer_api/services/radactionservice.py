from os import getenv

from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.DocumentPathMapper import DocumentPathMapper
from reviewer_api.models.default_method_result import DefaultMethodResult

from reviewer_api.services.redactionlayerservice import redactionlayerservice
from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.services.documentpageflagservice import documentpageflagservice
from reviewer_api.services.jobrecordservice import jobrecordservice
from reviewer_api.services.external.documentserviceproducerservice import documentserviceproducerservice

from reviewer_api.utils.util import to_json
from datetime import datetime

from xml.dom.minidom import parseString
import json

class redactionservice:
    """FOI Document management service"""


    
    def getannotationsbyrequest(
        self, ministryrequestid, _redactionlayer, page=None, size=None
    ):
        mappedlayerids = redactionlayerservice().getmappedredactionlayers(
            _redactionlayer
        )
        if page is not None and size is not None:
            return annotationservice().getrequestannotationspagination(
                ministryrequestid, mappedlayerids, page, size
            )
        return annotationservice().getrequestannotations(
            ministryrequestid, mappedlayerids
        )
    
    def getannotationsbydocument(self, ministryrequestid, _redactionlayer, documentid):
        mappedlayerids = redactionlayerservice().getmappedredactionlayers(
            _redactionlayer
        )
        return annotationservice().getdocumentannotations(ministryrequestid, mappedlayerids, documentid)

   
    def getannotationinfobyrequest(self, requestid, redactionlayer):
        return annotationservice().getrequestannotationinfo(requestid, redactionlayer)

    def copyannotation(self, ministryrequestid, targetlayer):
        sourcelayers = []
        sourcelayers.append(redactionlayerservice().getdefaultredactionlayerid())
        print(ministryrequestid)
        print(sourcelayers)
        print(targetlayer)
        return annotationservice().copyannotation(ministryrequestid, sourcelayers, targetlayer)

    def saveannotation(self, annotationschema, userinfo):
        result = annotationservice().saveannotation(annotationschema, userinfo)
        #pageflag logic
        if (
            result.success == True
            and "pageflags" in annotationschema
            and annotationschema["pageflags"] is not None
        ):
            foiministryrequestid = None
            if "foiministryrequestid" in annotationschema:
                foiministryrequestid = annotationschema["foiministryrequestid"]
            elif "sections" in annotationschema:
                foiministryrequestid = annotationschema["sections"][
                    "foiministryrequestid"
                ]
            if foiministryrequestid:
                bulkaddpageflagdata = self.__preparebulkaddpageflagdata(foiministryrequestid, annotationschema["pageflags"], annotationschema['redactionlayerid'])
                documentpageflagservice().bulksavepageflag(
                    foiministryrequestid,
                    bulkaddpageflagdata,
                    userinfo,
                )
        return result

    def deactivateannotation(
        self,
        annotationschema,
        userinfo,
        requestid,
        redactionlayerid,
    ):
        annotationnames = [
            anno["annotationname"] for anno in annotationschema["annotations"]
        ]
        result = annotationservice().deactivateannotation(
            annotationnames, redactionlayerid, userinfo
        )
        return result

    def deactivateredaction(
        self,
        annotationschema,
        userinfo,
        requestid,
        redactionlayerid,
    ):
        annotationnames = [
            anno["annotationname"] for anno in annotationschema["annotations"]
        ]
        result = annotationservice().deactivateannotation(
            annotationnames, redactionlayerid, userinfo
        )
        ### Remove/Update pageflags start here ###
        # totaldocumentpagesmapping docid and pages mapping for annotations deleted
        inputdocpagesmapping = self.__getdocumentpagesmapping(
            annotationschema["annotations"]
        )
        # find all active redactions for documents related to removed annotation. DB call to get the (document, pages, redaction) with redactions in it.
        documentactiveredactions = self.__getactivedocpagesmapping(
            inputdocpagesmapping, redactionlayerid
        )
        # create docmappings for pages with no active redactions remaining (to delete all page flags for docpageflag)
        deldocpagesmapping = self.__getdeldocpagesmapping(
            inputdocpagesmapping, documentactiveredactions
        )
        # create docmappings for pages with active redactions remaining (to update page flags for docpageflag)
        pageswithactiveredacitons = {
            (item["documentid"], item["pagenumber"]) for item in documentactiveredactions
        }
        docpageredcations = Annotation.getredactionannotationsbydocumentpages(pageswithactiveredacitons, redactionlayerid) if len(pageswithactiveredacitons) > 0 else []
        # update page flags for pages with redactions remaining (pageswithactiveredacitons) + pages not having any redactions remaining (deldocpagemapping)
        bulkupdateflagdata = self.__preparebulkupdatepageflagdata(pageswithactiveredacitons, docpageredcations, deldocpagesmapping)
        documentpageflagservice().bulkupdatepageflags(
            requestid,
            bulkupdateflagdata,
            redactionlayerid,
            userinfo
        )
        ### Remove/Update pageflags end here ###
        return result

    def __getactivedocpagesmapping(self, _documentpagesmapping, _redactionlayerid):
        activedata = []
        for item in _documentpagesmapping:
            docid = item["docid"]
            pages = item["pages"]
            activedata.extend(
                Annotation.getredactionsbydocumentpages(docid, pages, _redactionlayerid)
            )
        return activedata

    def __getdeldocpagesmapping(self, inputdocpagesmapping, skipdocpagesmapping):
        deldocpagesmapping = set()
        skip_combinations = {
            (item["documentid"], item["pagenumber"])
            for item in skipdocpagesmapping
            if len(skipdocpagesmapping) > 0
        }
        # Filter inputdocpagesmapping to obtain deletedocumentpagesmapping
        for item in inputdocpagesmapping:
            docid = item["docid"]
            if (len(item['pages']) > 0):
                for page in item['pages']:
                    if ((docid, page) not in skip_combinations):
                        deldocpagesmapping.add((docid, page))
        return deldocpagesmapping

    def __getdocumentpagesmapping(self, annotations):
        output_dict = {}
        for annotation in annotations:
            docid = annotation["docid"]
            page = annotation["page"] - 1  # in DB the page starts with 0
            if docid not in output_dict:
                output_dict[docid] = {"docid": docid, "pages": []}
            output_dict[docid]["pages"].append(page)
        output_list = list(output_dict.values())
        return output_list

    def getdocumentmapper(self, bucket):
        return DocumentPathMapper.getmapper(bucket)

    def gets3serviceaccount(self, documentpathid):
        mapper = DocumentPathMapper.getmapper(documentpathid)
        attribute = mapper["attributes"]
        return attribute

    def validateredactionlayer(self, redactionlayer, ministryrequestid):
        isvalid, _redactionlayer = redactionlayerservice().validateredactionlayer(
            redactionlayer, ministryrequestid
        )
        if isvalid == False:
            raise KeyError("Invalid redaction layer")
        return isvalid, _redactionlayer

    # redline/finalpackage download: add message to zipping service
    def triggerdownloadredlinefinalpackage(self, finalpackageschema, userinfo):
        _jobmessage = self.__preparemessageforjobstatus(finalpackageschema)
        job = jobrecordservice().insertpdfstitchjobstatus(
            _jobmessage, userinfo["userid"]
        )
        if job.success:
            _message = self.__preparemessageforsummaryservice(
                finalpackageschema, userinfo, job
            )
            return documentserviceproducerservice().add(_message)

    # redline/final package download: prepare message for zipping service
    def __preparemessageforsummaryservice(self, messageschema, userinfo, job):
        _message = {
            "jobid": job.identifier,
            "requestid": -1,
            "category": messageschema["category"],
            "requestnumber": messageschema["requestnumber"],
            "bcgovcode": messageschema["bcgovcode"],
            "createdby": userinfo["userid"],
            "ministryrequestid": messageschema["ministryrequestid"],
            "filestozip": to_json(
                self.__preparefilestozip(messageschema["attributes"])
            ),
            "finaloutput": to_json(""),
            "attributes": to_json(messageschema["attributes"]),
            "summarydocuments": json.dumps(messageschema["summarydocuments"]),
            "redactionlayerid": json.dumps(messageschema["redactionlayerid"])
        }
        return _message

    # redline/final package download: prepare message for zipping service
    def __preparefilestozip(self, attributes):
        filestozip = []
        for attribute in attributes:
            for file in attribute["files"]:
                _file = {
                    "filename": file["filename"],
                    "s3uripath": file["s3uripath"],
                }
                filestozip.append(_file)
        return filestozip

    # redline/final package download: prepare message for redline/final package job status
    def __preparemessageforjobstatus(self, messageschema):
        __message = {
            "category": messageschema["category"],
            "ministryrequestid": int(messageschema["ministryrequestid"]),
            "inputfiles": messageschema["attributes"],
        }
        return __message

    def __preparebulkaddpageflagdata(self, requestid, annot_pageflags, redactionlayerid):
        docids = [doc['documentid'] for doc in annot_pageflags['documentpageflags']]
        docpreviousflags = documentpageflagservice().getdocumentpageflagsbydocids(requestid, redactionlayerid, docids)
        for i in range(len(annot_pageflags['documentpageflags'])):
            doc = annot_pageflags['documentpageflags'][i]
            for j in range(len(doc['pageflags'])):
                pageflag = doc['pageflags'][j]
                #loop through previous docplageflag data, find assoacited docpageflags using docid and see if withheld in full page flag (flagid 3) exists for the new annotations page
                for docpageobj in docpreviousflags:
                    if (doc['documentid'] == docpageobj['documentid'] and {"page": pageflag['page'], "flagid": 3} in docpageobj['pageflag']):
                        annot_pageflags['documentpageflags'][i]['pageflags'][j] = {"page": pageflag['page'], "flagid": 3}            
        return annot_pageflags
    
    def __preparebulkupdatepageflagdata(self, pageswithactiveredacitons, docpageredcations, deldocpagesmapping):
        # page + 1 because in DB pages start at 1
        bulkupdatedata = {}
        # loop through set of docpagemappings to delete/remove page flags
        for docid, page in deldocpagesmapping:
            newpageflag = {"page": page + 1, "flagid": None}
            if (docid not in bulkupdatedata):
                bulkupdatedata[docid] = {"docid": docid, "pageflag": []}
            bulkupdatedata[docid]['pageflag'].append(newpageflag)
        # loop through set of pages with redaction remaining in them to update pageflags to partial or withehld in full
        for docid, page in pageswithactiveredacitons:
            for docobj in docpageredcations:
                if (docid == docobj['documentid'] and page == docobj['pagenumber']):
                    redactions = docobj['annotations']
                    flagid = self.__createflagidfromredactions(redactions)
                    newpageflag = {"page": page + 1, "flagid": flagid}
                    if (docid not in bulkupdatedata):
                        bulkupdatedata[docid] = {"docid": docid, "pageflag": []}
                    bulkupdatedata[docid]['pageflag'].append(newpageflag)
        return list(bulkupdatedata.values())
    
    def __createflagidfromredactions(self, redactions):
        # conditional to check if fullpage xml data exists in a pages redaction (if it does -> flagid of 3 is applied else flagid of)
        if (any(
            'trn-redaction-type' in json.loads(parseString(redaction).getElementsByTagName("trn-custom-data")[0].getAttribute("bytes")) 
            and json.loads(parseString(redaction).getElementsByTagName("trn-custom-data")[0].getAttribute("bytes"))['trn-redaction-type'] == 'fullPage'
            for redaction in redactions
        )):
            flagid = 3
        else:
            flagid = 1
        return flagid
        
