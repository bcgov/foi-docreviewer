
from os import stat
from re import VERBOSE
from reviewer_api.models.Documents import Document
from reviewer_api.models.Annotations import Annotation


from reviewer_api.models.OperatingTeamS3ServiceAccounts import OperatingTeamS3ServiceAccount
from reviewer_api.models.DocumentPathMapper import DocumentPathMapper
from reviewer_api.services.redactionlayerservice import redactionlayerservice

from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.services.documentpageflagservice import documentpageflagservice
import json
import os
import base64

import xml.etree.ElementTree as ET

class redactionservice:
    """ FOI Document management service
    """
    
    def getannotations(self, documentid, documentversion, pagenumber):
        return annotationservice().getannotations(documentid, documentversion, pagenumber)
    
    def getannotationsbyrequest(self, ministryrequestid, _redactionlayer):
        mappedlayerids = redactionlayerservice().getmappedredactionlayers(_redactionlayer)
        return annotationservice().getrequestannotations(ministryrequestid, mappedlayerids)
    
    def getannotationsbyrequestdivision(self, ministryrequestid, divisionid):
        return annotationservice().getrequestdivisionannotations(ministryrequestid, divisionid)

    def getannotationinfo(self, documentid, documentversion, pagenumber):
        return annotationservice().getannotationinfo(documentid, documentversion, pagenumber)

    def getannotationinfobyrequest(self, requestid):
        return annotationservice().getrequestannotationinfo(requestid)


    def saveannotation(self, annotationschema, userinfo):
         result= annotationservice().saveannotation(annotationschema,userinfo)
         if result.success == True and "foiministryrequestid" in annotationschema and "pageflags" in annotationschema and annotationschema["pageflags"] is not None:
            documentpageflagservice().bulksavepageflag(annotationschema["foiministryrequestid"], annotationschema["pageflags"], userinfo)
         return result

    def deactivateannotation(self, annotationname, documentid, documentversion, userinfo,requestid, page):
        result =  annotationservice().deactivateannotation(annotationname, documentid, documentversion, userinfo)
        if result.success == True and page is not None:
            documentpageflagservice().removepageflag(requestid, documentid, documentversion, page, userinfo)
        return result

    def deactivateredaction(self, annotationname, documentid, documentversion, userinfo,requestid, page):
        result = annotationservice().deactivateannotation(annotationname, documentid, documentversion, userinfo)
        if result.success == True:
            newresult = Annotation.getredactionsbypage(documentid, documentversion, page)
            if len(newresult) == 0:
                documentpageflagservice().removepageflag(requestid, documentid, documentversion, page, userinfo)
        return result

    def getdocumentmapper(self, bucket):
        return DocumentPathMapper.getmapper(bucket)

    def gets3serviceaccount(self, documentpathid):
        mapper =  DocumentPathMapper.getmapper(documentpathid)
        attribute = mapper["attributes"]
        return attribute

    def validateredactionlayer(self, redactionlayer, ministryrequestid):
        isvalid, _redactionlayer = redactionlayerservice().validateredactionlayer(redactionlayer, ministryrequestid)
        if isvalid == False:
            raise KeyError("Invalid redaction layer")
        return isvalid, _redactionlayer