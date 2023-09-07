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


class redactionservice:
    """FOI Document management service"""

    zipperstreamkey = getenv("ZIPPER_STREAM_KEY")

    def getannotations(self, documentid, documentversion, pagenumber):
        return annotationservice().getannotations(
            documentid, documentversion, pagenumber
        )

    def getannotationsbyrequest(self, ministryrequestid, _redactionlayer):
        mappedlayerids = redactionlayerservice().getmappedredactionlayers(
            _redactionlayer
        )
        return annotationservice().getrequestannotations(
            ministryrequestid, mappedlayerids
        )

    def getannotationsbyrequestdivision(self, ministryrequestid, divisionid):
        return annotationservice().getrequestdivisionannotations(
            ministryrequestid, divisionid
        )

    def getannotationinfo(self, documentid, documentversion, pagenumber):
        return annotationservice().getannotationinfo(
            documentid, documentversion, pagenumber
        )

    def getannotationinfobyrequest(self, requestid):
        return annotationservice().getrequestannotationinfo(requestid)

    def saveannotation(self, annotationschema, userinfo):
        result = annotationservice().saveannotation(annotationschema, userinfo)
        if (
            result.success == True
            and "foiministryrequestid" in annotationschema
            and "pageflags" in annotationschema
            and annotationschema["pageflags"] is not None
        ):
            documentpageflagservice().bulksavepageflag(
                annotationschema["foiministryrequestid"],
                annotationschema["pageflags"],
                userinfo,
            )
        return result

    def deactivateannotation(
        self,
        annotationname,
        documentid,
        documentversion,
        userinfo,
        requestid,
        page,
        redactionlayerid,
    ):
        result = annotationservice().deactivateannotation(
            annotationname, redactionlayerid, userinfo
        )
        if result.success == True and page is not None:
            documentpageflagservice().removepageflag(
                requestid, documentid, documentversion, page, redactionlayerid, userinfo
            )
        return result

    def deactivateredaction(
        self,
        annotationname,
        documentid,
        documentversion,
        userinfo,
        requestid,
        page,
        redactionlayerid,
    ):
        result = annotationservice().deactivateannotation(
            annotationname, redactionlayerid, userinfo
        )
        if result.success == True:
            newresult = Annotation.getredactionsbypage(
                documentid, documentversion, page, redactionlayerid
            )
            if len(newresult) == 0:
                documentpageflagservice().removepageflag(
                    requestid,
                    documentid,
                    documentversion,
                    page,
                    redactionlayerid,
                    userinfo,
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
            _message = self.__preparemessageforzipservice(
                finalpackageschema, userinfo, job
            )
            print(_message)
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
