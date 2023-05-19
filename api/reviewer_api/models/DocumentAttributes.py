from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime as datetime2
import logging

class DocumentAttributes(db.Model):
    __tablename__ = 'DocumentAttributes' 
    # Defining the columns
    attributeid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    documentmasterid = db.Column(db.Integer, db.ForeignKey('DocumentMaster.documentmasterid'))
    attributes = db.Column(JSON, unique=False, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)

    @classmethod
    def getdocumentattributes(cls, documentid):
        try:
            attributes_schema = DocumentAttributeSchema(many=True)
            query = db.session.query(DocumentAttributes).filter_by(and_(documentid = documentid)).order_by(DocumentAttributes.documentversion.desc()).first()
            return attributes_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def create(cls, row):
        try:
            db.session.add(row)
            db.session.commit()
            return DefaultMethodResult(True,'Attributes added for document master id Added: {0}'.format(row.documentmasterid), row.attributeid)    
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
        
class DocumentAttributeSchema(ma.Schema):
    class Meta:
        fields = ('attributeid', 'documentmasterid', 'documentversion','attributes','createdby','created_at')