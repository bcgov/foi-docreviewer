from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import and_
from datetime import datetime as datetime2
import logging

class DocumentPathMapper(db.Model):
    __tablename__ = 'DocumentPathMapper' 
    # Defining the columns
    documentpathid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.Text, unique=False, nullable=False)
    bucket = db.Column(db.Text, unique=False, nullable=False)
    attributes = db.Column(db.Text, unique=False, nullable=True)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(db.String(120), unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def getmapper(cls, bucket):
        try:
            documentpathmapperschema = DocumentPathMapperSchema(many=False)
            query = db.session.query(DocumentPathMapper).filter(DocumentPathMapper.bucket == bucket).first()
            return documentpathmapperschema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

class DocumentPathMapperSchema(ma.Schema):
    class Meta:
        fields = ('documentpathid', 'category', 'bucket', 'attributes', 'isactive', 'createdby', 'created_at', 'updatedby', 'updated_at')