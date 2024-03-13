from .db import db, ma
from datetime import datetime as datetime2
from sqlalchemy.dialects.postgresql import JSON, insert
from sqlalchemy import or_, and_, text
from .default_method_result import DefaultMethodResult
from reviewer_api.models.Documents import Document
import logging

class DocumentDeletedPage(db.Model):
    __tablename__ = 'DocumentDeletedPages'
    # Defining the columns
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    redactionlayerid = db.Column(db.Integer, primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)  
    documentid = db.Column(db.Integer, nullable=False)      
    pagemetadata = db.Column(JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    createdby = db.Column(JSON, unique=False, nullable=False)

    
    @classmethod
    def create(cls, ministryrequestid, docpages, pagemappings) -> DefaultMethodResult:
        try:
            insertstmt = insert(DocumentDeletedPage).values(docpages)
            db.session.execute(insertstmt)       
            db.session.bulk_update_mappings(Document, pagemappings)     
            db.session.commit()
            return DefaultMethodResult(True, "Deleted page details saved", ministryrequestid)
        except Exception as ex:
            logging.error(ex)
            return DefaultMethodResult(False, "Deleted page details persist operation failed", ministryrequestid)
        finally:
            db.session.close()

    @classmethod
    def getdeletedpages(cls, ministryrequestid, docids):
        try:
            deletepage_schema = DocumentDeletedSchema(many=True)
            query = db.session.query(DocumentDeletedPage).filter(DocumentDeletedPage.ministryrequestid == ministryrequestid, DocumentDeletedPage.documentid.in_(docids)).all()
            return deletepage_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

     
class DocumentDeletedSchema(ma.Schema):
    class Meta:
        fields = ('id', 'version', 'redactionlayerid', 'ministryrequestid', 'documentid','pagemetadata', 'created_at', 'createdby')