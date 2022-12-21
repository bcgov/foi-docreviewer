from reviewer_api.models.Documents import Document
from datetime import datetime as datetime2
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

        return documents

    def deletedocument(self, filepath, userid):
        """ Inserts document into list of deleted documents
        """
        deleteddocument = DocumentDeleted(filepath=filepath, deleted=True, createdby=userid, created_at=datetime2.now())
        return DocumentDeleted.create(deleteddocument)
