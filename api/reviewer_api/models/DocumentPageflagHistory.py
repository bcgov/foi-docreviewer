from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_
from datetime import datetime as datetime2
from sqlalchemy.sql.schema import ForeignKey, ForeignKeyConstraint
import logging
from sqlalchemy.dialects.postgresql import JSON, insert
from datetime import datetime
from sqlalchemy import or_, and_
from sqlalchemy import text
from sqlalchemy.orm import relationship, backref

class DocumentPageflagHistory(db.Model):
  
    __tablename__ = 'DocumentPageflagHistory' 
    constraint_pg = db.Index("constraint_pg", 'foiministryrequestid', 'documentid','documentversion')
    # Defining the columns
    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    documentpageflagid = db.Column(db.Integer, primary_key=True)
    foiministryrequestid = db.Column(db.Integer, nullable=False)
    documentid = db.Column(db.Integer, ForeignKey('Documents.documentid')) 
    documentversion = db.Column(db.Integer, ForeignKey('Documents.version'))
    pageflag = db.Column(db.Text, unique=False, nullable=False)  
    attributes = db.Column(db.Text, unique=False, nullable=True)  
    createdby = db.Column(db.Text, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(db.Text, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    redactionlayerid = db.Column(db.Integer, db.ForeignKey('RedactionLayers.redactionlayerid'))

    @classmethod
    def createpageflag(cls, documentpageflaghistory)->DefaultMethodResult:
        # no db close or commit because this function is called in a loop
        try:
            db.session.add(documentpageflaghistory)
            db.session.commit()
            return DefaultMethodResult(True, 'Page Flag history is saved', documentpageflaghistory.id)  
        except Exception as ex:
            logging.error(ex)
            return DefaultMethodResult(False, 'Page Flag history is not saved', documentpageflaghistory.id)
        finally:
            db.session.close()