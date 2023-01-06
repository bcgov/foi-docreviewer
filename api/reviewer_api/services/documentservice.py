from reviewer_api.models.Documents import Document
from reviewer_api.models.FileConversionJob import FileConversionJob
from reviewer_api.models.DeduplicationJob import DeduplicationJob
from datetime import datetime as datetime2
from os import path
from reviewer_api.models.DocumentDeleted import DocumentDeleted
import json
from reviewer_api.utils.util import pstformat

class documentservice:

    def getdedupestatus(self, requestid):
        """ Returns the active records
        """
        documents = Document.getdocumentsdedupestatus(requestid)
        for document in documents:
            document['created_at'] = pstformat(document['created_at'])
            document['updated_at'] = pstformat(document['updated_at'])

        filesconverted, conversionerrors = FileConversionJob.getfilesconverted(requestid)
        filesdeduped, dedupeerrors = DeduplicationJob.getfilesdeduped(requestid)

        return {"documents": documents, "filesconverted":filesconverted, "filesdeduped": filesdeduped, "conversionerrors": conversionerrors, "dedupeerrors": dedupeerrors}

    def deletedocument(self, filepath, userid):
        """ Inserts document into list of deleted documents
        """
        filepath, _extension = path.splitext(filepath)
        deleteddocument = DocumentDeleted(filepath=filepath, deleted=True, createdby=userid, created_at=datetime2.now())
        return DocumentDeleted.create(deleteddocument)
