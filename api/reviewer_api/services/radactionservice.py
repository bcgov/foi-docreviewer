
from os import stat
from re import VERBOSE
from reviewer_api.models.Documents import Document
from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.OperatingTeamS3ServiceAccounts import OperatingTeamS3ServiceAccount

import json
import base64
import maya

class redactionservice:
    """ FOI Document management service
    """
    
    def getdocuments(self, requestid):
        documents = Document.getdocuments(requestid)
        return documents
    
    def savedocument(self, documentid, documentversion, newfilepath, userid):
        return

    def deleterequestdocument(self, documentid, documentversion):
        return

    def getannotations(self, documentid, documentversion):
        annotations = Annotation.getannotations(documentid, documentversion)
        return self.__formatcreateddate(annotations)

    def saveannotation(self, documentid, documentversion, annotation, pagenumber, createdby):
        return Annotation.saveannotation(documentid, documentversion, annotation, pagenumber, createdby)

    def gets3serviceaccount(self, groupname):
        return OperatingTeamS3ServiceAccount.getserviceaccount(groupname)

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