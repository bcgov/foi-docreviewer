
from os import stat
from re import VERBOSE
from reviewer_api.models.Documents import Document
from reviewer_api.models.Annotations import Annotation


from reviewer_api.models.OperatingTeamS3ServiceAccounts import OperatingTeamS3ServiceAccount
from reviewer_api.models.DocumentPathMapper import DocumentPathMapper
from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.services.documentpageflagservice import documentpageflagservice
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
    
    def getannotationsbyrequest(self, ministryrequestid):
        return annotationservice().getrequestannotations(ministryrequestid)
    
    def getannotationsbyrequestdivision(self, ministryrequestid, divisionid):
        return annotationservice().getrequestdivisionannotations(ministryrequestid, divisionid)

    def getannotationinfo(self, documentid, documentversion, pagenumber):
        return annotationservice().getannotationinfo(documentid, documentversion, pagenumber)

    def getannotationinfobyrequest(self, requestid):
        return annotationservice().getrequestannotationinfo(requestid)


    def saveannotation(self, documentid, documentversion, annotationschema, userinfo):
         result= annotationservice().saveannotation(documentid, documentversion, annotationschema,userinfo)
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

    def __formatcreateddate(self, items):
        for element in items:
            element = self.__pstformat(element)
        return items

    def __pstformat(self, element):
        formatedcreateddate = maya.parse(element['created_at']).datetime(to_timezone='America/Vancouver', naive=False)
        element['created_at'] = formatedcreateddate.strftime('%Y %b %d | %I:%M %p')
        return element

    def __extractannotfromxml(self, xmlstring):
        firstlist = xmlstring.split('<annots>')
        if len(firstlist) == 2: 
            secondlist = firstlist[1].split('</annots>')
            return secondlist[0]
        return ''
    
    def __generateannotationsxml(self, annotations):
        if not annotations:
            return ''

        annotationsstring = ''.join(annotations)

        template_path = "reviewer_api/xml_templates/annotations.xml"
        file_dir = os.path.dirname(os.path.realpath('__file__'))
        full_template_path = os.path.join(file_dir, template_path)
        f = open(full_template_path, "r")

        xmltemplatelines = f.readlines()
        xmltemplatestring = ''.join(xmltemplatelines)

        return xmltemplatestring.replace("{{annotations}}", annotationsstring)
