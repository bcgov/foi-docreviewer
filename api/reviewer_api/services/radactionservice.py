
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

    # def uploadpersonaldocuments(self, requestid, attachments):
    #     attachmentlist = []
    #     if attachments:
    #         for attachment in attachments:
    #             attachment['filestatustransition'] = 'personal'
    #             attachment['ministrycode'] = 'Misc'
    #             attachment['requestnumber'] = str(requestid)
    #             attachment['file'] = base64.b64decode(attachment['base64data'])
    #             attachment.pop('base64data')
    #             attachmentresponse = storageservice().upload(attachment)
    #             attachmentlist.append(attachmentresponse)
                
    #         documentschema = CreateDocumentSchema().load({'documents': attachmentlist})
    #         return self.createrequestdocument(requestid, documentschema, None, "rawrequest")        

    # def getattachments(self, requestid, requesttype, category):        
    #     documents = self.getlatestdocumentsforemail(requestid, requesttype, category)  
    #     if(documents is None):
    #         raise ValueError('No template found')
    #     attachmentlist = []
    #     for document in documents:  
    #         filename = document.get('filename')
    #         s3uri = document.get('documentpath')
    #         attachment= storageservice().download(s3uri)
    #         attachdocument = {"filename": filename, "file": attachment, "url": s3uri}
    #         attachmentlist.append(attachdocument)
    #     return attachmentlist

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
