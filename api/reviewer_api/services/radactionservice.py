from os import getenv

from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.DocumentPathMapper import DocumentPathMapper
from reviewer_api.models.default_method_result import DefaultMethodResult

from reviewer_api.services.redactionlayerservice import redactionlayerservice
from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.services.documentpageflagservice import documentpageflagservice
from reviewer_api.services.jobrecordservice import jobrecordservice
from reviewer_api.services.external.zipperproducerservice import zipperproducerservice

from reviewer_api.utils.util import to_json
from datetime import datetime
from xml.dom.minidom import parseString
import json


class redactionservice:
    """FOI Document management service"""

    zipperstreamkey = getenv("ZIPPER_STREAM_KEY")

    
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
                bulkaddpageflagdata = self.__preparebulkpageflagdata(foiministryrequestid, annotationschema["pageflags"], annotationschema['redactionlayerid'])
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
        # totaldocumentpagesmapping docid and pages mapping
        inputdocpagesmapping = self.__getdocumentpagesmapping(
            annotationschema["annotations"]
        )
        # find all active redactions for documents related to removed annotation. DB call to get the (document, pages, redaction) with redactions in it.
        documentactiveredactions = self.__getskipdocpagesmapping(
            inputdocpagesmapping, redactionlayerid
        )
        # update page flags for pages with redactions remaining
        pageswithactiveredacitons = {
            (item["documentid"], item["pagenumber"]) for item in documentactiveredactions
        }
        if (len(pageswithactiveredacitons) > 0):
            bulkupdateflagdata = []
            docpageredcations = Annotation.getredactionannotationsbydocumentpages(pageswithactiveredacitons, redactionlayerid) 
            for docid, page in pageswithactiveredacitons:
                for docobj in docpageredcations:
                    if (docid == docobj['documentid'] and page == docobj['pagenumber']):
                        redactions = docobj['annotations']
                        if (any(
                            'trn-redaction-type' in json.loads(parseString(redaction).getElementsByTagName("trn-custom-data")[0].getAttribute("bytes")) 
                            and json.loads(parseString(redaction).getElementsByTagName("trn-custom-data")[0].getAttribute("bytes"))['trn-redaction-type'] == 'fullPage'
                            for redaction in redactions
                        )):
                            bulkupdateflagdata.append({
                                "docid": docid,
                                #in DB, pages start at 1
                                "pageflag": {"page": page + 1, "flagid": 3}
                            })
                        else:
                            bulkupdateflagdata.append({
                                "docid": docid,
                                "pageflag": {"page": page + 1, "flagid": 1}
                            })
            documentpageflagservice().updatepageflags_redactions_remaining(
                requestid,
                bulkupdateflagdata,
                redactionlayerid,
                userinfo
            )
        # update page flags for pages not having any redactions remaining (skip all pages that have remaining redactions)
        deldocpagesmapping = self.__getdeldocpagesmapping(
            inputdocpagesmapping, documentactiveredactions
        )
        if deldocpagesmapping:
            documentpageflagservice().updatepageflags(
                requestid,
                deldocpagesmapping,
                redactionlayerid,
                userinfo,
            )
        ### Remove/Update pageflags end here ###
        return result

    def __getskipdocpagesmapping(self, _documentpagesmapping, _redactionlayerid):
        skipdata = []
        # gets the documentid and pages to skip based on documentid and pages
        for item in _documentpagesmapping:
            docid = item["docid"]
            pages = item["pages"]
            skipdata.extend(
                Annotation.getredactionsbydocumentpages(docid, pages, _redactionlayerid)
            )
        return skipdata

    def __getdeldocpagesmapping(self, inputdocpagesmapping, skipdocpagesmapping):
        #  item["pagenumber"] + 1 is because the page in pageflags starts with 1
        skip_combinations = {
            (item["documentid"], item["pagenumber"])
            for item in skipdocpagesmapping
            if len(skipdocpagesmapping) > 0
        }

        # Filter inputdocpagesmapping to obtain deletedocumentpagesmapping
        deldocpagesmapping = [
            {
                "docid": item["docid"],
                "pages": [
                    page + 1
                    for page in item["pages"]
                    if (item["docid"], page) not in skip_combinations
                ],
            }
            for item in inputdocpagesmapping
            if len(item["pages"]) > 0
        ]
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
            _message = self.__preparemessageforzipservice(
                finalpackageschema, userinfo, job
            )
            return zipperproducerservice().add(self.zipperstreamkey, _message)

    # redline/final package download: prepare message for zipping service
    def __preparemessageforzipservice(self, messageschema, userinfo, job):
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
            "finaloutput": to_json({}),
            "attributes": to_json(messageschema["attributes"]),
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

    def __preparebulkpageflagdata(self, requestid, annot_pageflags, redactionlayerid):
        docids = [doc['documentid'] for doc in annot_pageflags['documentpageflags']]
        docpreviousflags = documentpageflagservice().getdocumentpageflagsbydocids(requestid, redactionlayerid, docids)
        #loop through new annotations docs
        for i in range(len(annot_pageflags['documentpageflags'])):
            doc = annot_pageflags['documentpageflags'][i]
            #loop through new annotations doc pageflags
            for j in range(len(doc['pageflags'])):
                pageflag = doc['pageflags'][j]
                #loop through previous docplageflag data, find assoacited docpageflags using docid and see if withheld in full page flag (flagid 3) exists for the new annotations page
                for docpageobj in docpreviousflags:
                    if (doc['documentid'] == docpageobj['documentid'] and {"page": pageflag['page'], "flagid": 3} in docpageobj['pageflag']):
                        annot_pageflags['documentpageflags'][i]['pageflags'][j] = {"page": pageflag['page'], "flagid": 3}
                    
        return annot_pageflags
        
