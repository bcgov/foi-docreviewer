from reviewer_api.models.Documents import Document
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.FileConversionJob import FileConversionJob
from reviewer_api.models.DeduplicationJob import DeduplicationJob
from datetime import datetime as datetime2
from os import path
from reviewer_api.models.DocumentDeleted import DocumentDeleted
import json
from reviewer_api.utils.util import pstformat
from reviewer_api.models.ProgramAreaDivisions import ProgramAreaDivision

class documentservice:

    def getdedupestatus(self, requestid):
        """ Returns the active records
        """
        documents = Document.getdocumentsdedupestatus(requestid)
        for document in documents:
            document['created_at'] = pstformat(document['created_at'])
            document['updated_at'] = pstformat(document['updated_at'])

        return documents

    def deletedocument(self, filepaths, userid):
        """ Inserts document into list of deleted documents
        """
        return DocumentDeleted.create([
            DocumentDeleted(
                filepath=path.splitext(filepath)[0],
                deleted=True,
                createdby=userid,
                created_at=datetime2.now()
            ) for filepath in filepaths
        ])


    def getdocuments(self, requestid):
        documents = Document.getdocuments(requestid)
        divisions = ProgramAreaDivision.getallprogramareadivisons() # TODO: What cant we filter by ministry?

        formated_documents = []
        for document in documents:
            doc_divisions = []
            for division in document['divisions']:
                doc_division = [div for div in divisions if div['divisionid']==division['divisionid']][0]
                doc_divisions.append(doc_division)

            document['divisions'] = doc_divisions
            formated_documents.append(document)

        return documents
    
    def getdocument(self, documentid):
        return Document.getdocument(documentid)    
    
    
    def savedocument(self, documentid, documentversion, newfilepath, userid):
        return

    def deleterequestdocument(self, documentid, documentversion):
        return
