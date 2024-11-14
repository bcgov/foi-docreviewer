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
        return annotationservice().copyannotation(ministryrequestid, sourcelayers, targetlayer)

    def saveannotation(self, annotationschema, userinfo):
        pageflagresponse= None
        result = annotationservice().saveannotation(annotationschema, userinfo)
        redactionlayer=redactionlayerservice().getredactionlayerbyid(annotationschema['redactionlayerid'])
        #Condition to ignore saving pageflags to db for OI layer
        #whenever a redaction is made.
        openinfolayer= redactionlayerservice().isopeninfolayer(redactionlayer['name'])
        if (
            result.success == True
            and "pageflags" in annotationschema
            and annotationschema["pageflags"] is not None
            and openinfolayer == False
        ):
            foiministryrequestid = None
            if "foiministryrequestid" in annotationschema:
                foiministryrequestid = annotationschema["foiministryrequestid"]
            elif "sections" in annotationschema:
                foiministryrequestid = annotationschema["sections"][
                    "foiministryrequestid"
                ]
            if foiministryrequestid:
                pageflagresponse= documentpageflagservice().bulksavepageflag(
                    foiministryrequestid,
                    annotationschema["pageflags"],
                    userinfo,
                )
        return pageflagresponse, result

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
        return result

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
            if 'pdfstitchjobattributes' in finalpackageschema and finalpackageschema['pdfstitchjobattributes'] is not None:
                if 'feeoverridereason' in finalpackageschema['pdfstitchjobattributes']:
                    feeoverridereason= finalpackageschema['pdfstitchjobattributes']['feeoverridereason']
                    if feeoverridereason is not None and feeoverridereason != '':
                        jobrecordservice().insertfeeoverridereason(finalpackageschema,job.identifier,userinfo["userid"])
            _message = self.__preparemessageforsummaryservice(
                finalpackageschema, userinfo, job
            )
            return documentserviceproducerservice().add(_message)

    # redline/final package download: prepare message for zipping service
    def __preparemessageforsummaryservice(self, messageschema, userinfo, job):
        feeoverridereason= ''
        pdf_stitch_job_attributes = None
        if 'pdfstitchjobattributes' in messageschema:
            pdf_stitch_job_attributes = to_json(messageschema['pdfstitchjobattributes'])
        if pdf_stitch_job_attributes is not None:
            feeoverridereason= json.loads(pdf_stitch_job_attributes).get("feeoverridereason", None) 
            if feeoverridereason is not None and feeoverridereason != '':
                feeoverridereason= userinfo["firstname"]+" "+userinfo["lastname"]+" overrode balance outstanding warning for the following reason: "+feeoverridereason
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
            "redactionlayerid": json.dumps(messageschema["redactionlayerid"]),
            "requesttype": messageschema["requesttype"],
            "feeoverridereason":feeoverridereason
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