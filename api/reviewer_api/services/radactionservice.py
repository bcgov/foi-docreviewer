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
            annotationname, documentid, documentversion, userinfo
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
            annotationname, documentid, documentversion, userinfo
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

    # redline download: add message to zipping service
    def triggerdownloadredline(self, redlineschema, userinfo):
        _jobmessage = self.__preparemessageforredlinejobstatus(redlineschema)
        job = jobrecordservice().insertpdfstitchjobstatus(
            _jobmessage, userinfo["userid"]
        )
        print(job)
        if job.success:
            _message = self.__preparemessageforzipservice(redlineschema, userinfo, job)
            print(_message)
            return zipperproducerservice().add(self.zipperstreamkey, _message)

    # redline download: prepare message for zipping service
    def __preparemessageforzipservice(self, redlineschema, userinfo, job):
        _message = {
            "jobid": job.identifier,
            "requestid": -1,
            "category": redlineschema["category"],
            "requestnumber": redlineschema["requestnumber"],
            "bcgovcode": redlineschema["bcgovcode"],
            "createdby": userinfo["userid"],
            "ministryrequestid": redlineschema["ministryrequestid"],
            "filestozip": to_json(
                self.__preparefilestozip(redlineschema["attributes"])
            ),
            "finaloutput": to_json({}),
            "attributes": to_json(redlineschema["attributes"]),
        }
        return _message

    # redline download: prepare message for zipping service
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

    # redline download: prepare message for redline job status
    def __preparemessageforredlinejobstatus(self, redlineschema):
        __message = {
            "category": redlineschema["category"],
            "ministryrequestid": int(redlineschema["ministryrequestid"]),
            "inputfiles": redlineschema["attributes"],
        }
        return __message
