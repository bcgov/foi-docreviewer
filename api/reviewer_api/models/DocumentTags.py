from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime as datetime2

class DocumentTag(db.Model):
    __tablename__ = 'DocumentTags' 
    # Defining the columns
    tagid = db.Column(db.Integer, primary_key=True,autoincrement=True)
    documentid = db.Column(db.Integer, db.ForeignKey('Documents.documentid'))
    documentversion = db.Column(db.Integer, db.ForeignKey('Documents.version'))
    tag = db.Column(JSON, unique=False, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)

    @classmethod
    def getdocumenttags(cls, documentid):
        documenttag_schema = DocumentTagSchema(many=True)
        query = db.session.query(DocumentTag).filter_by(and_(documentid = documentid)).order_by(DocumentTag.documentversion.desc()).first()
        return documenttag_schema.dump(query)

class DocumentTagSchema(ma.Schema):
    class Meta:
        fields = ('tagid', 'documentid', 'documentversion','tag','createdby','created_at')