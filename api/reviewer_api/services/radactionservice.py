
from os import stat
from re import VERBOSE
from reviewer_api.models.Documents import Document
from reviewer_api.models.Annotations import Annotation


from reviewer_api.models.OperatingTeamS3ServiceAccounts import OperatingTeamS3ServiceAccount
from reviewer_api.models.DocumentPathMapper import DocumentPathMapper
from reviewer_api.services.annotationservice import annotationservice
import json
import os
import base64
import maya

import xml.etree.ElementTree as ET

class redactionservice:
    """ FOI Document management service
    """
    
    def getannotations(self, documentid, documentversion, pagenumber):
        return annotationservice().getannotations(documentid, documentversion, pagenumber)

    def getannotationinfo(self, documentid, documentversion, pagenumber):
        return annotationservice().getannotationinfo(documentid, documentversion, pagenumber)


    def saveannotation(self, annotationname, documentid, documentversion, annotationschema, pagenumber, userinfo):
        return annotationservice().saveannotation(annotationname, documentid, documentversion, annotationschema, pagenumber, userinfo)

    def deactivateannotation(self, annotationname, documentid, documentversion, userinfo):
        return annotationservice().deactivateannotation(annotationname, documentid, documentversion, userinfo)

    def getdocumentmapper(self, documentpathid):
        return DocumentPathMapper.getmapper(documentpathid)

    def gets3serviceaccount(self, documentpathid):
        mapper =  DocumentPathMapper.getmapper(documentpathid)
        # print(mapper["attributes"])
        attribute = mapper["attributes"]
        # print(attribute)
        return attribute
