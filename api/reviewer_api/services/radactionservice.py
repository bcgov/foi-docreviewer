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
                documentpageflagservice().bulksavepageflag(
                    foiministryrequestid,
                    annotationschema["pageflags"],
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
        print(f"<<< start getredactionsbydocuments >>> {datetime.now()}")
        # skip the pages as it has redactions in it. DB call to get the (document, pages) with redactions in it.
        skipdocpagesmapping = Annotation.getredactionsbydocuments(
            inputdocpagesmapping, redactionlayerid
        )
        print(f"<<< end getredactionsbydocuments >>> {datetime.now()}")
        # pages not having redactions
        deldocpagesmapping = self.__getdeldocpagesmapping(
            inputdocpagesmapping, skipdocpagesmapping
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

    def __getdeldocpagesmapping(self, inputdocpagesmapping, skipdocpagesmapping):
        #  item["pagenumber"] + 1 is because the page in pageflags starts with 1
        skip_combinations = {
            (item["documentid"], item["pagenumber"]) for item in skipdocpagesmapping
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
        # Iterate through the annotations and organize the data
        for annotation in annotations:
            docid = annotation["docid"]
            page = annotation["page"] - 1  # in DB the page starts with 0

            # If docid is not in the output_dict, create an entry with an empty list of pages
            if docid not in output_dict:
                output_dict[docid] = {"docid": docid, "pages": []}

            # Append the page to the list of pages for the corresponding docid
            output_dict[docid]["pages"].append(page)

        # Convert the values of the output_dict into a list
        output_list = list(output_dict.values())

        # Print the resulting list
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
