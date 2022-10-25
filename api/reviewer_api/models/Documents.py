from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime as datetime2
from sqlalchemy.orm import relationship, backref
from sqlalchemy import func
from .DocumentStatus import DocumentStatus
from .DocumentTags import DocumentTag
from reviewer_api.utils.util import pstformat

class Document(db.Model):
    __tablename__ = 'Documents' 
    # Defining the columns
    documentid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    filename = db.Column(db.String(120), unique=False, nullable=False)
    filepath = db.Column(db.String(255), unique=False, nullable=False)
    attributes = db.Column(JSON, unique=False, nullable=True)
    foiministryrequestid = db.Column(db.Integer, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(JSON, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    statusid = db.Column(db.Integer, db.ForeignKey('DocumentStatus.statusid'))
    documentstatus = relationship("DocumentStatus", backref=backref("DocumentStatus"), uselist=False)

    @classmethod
    def getdocuments(cls, foiministryrequestid):
        _session = db.session

        #subquery for getting latest version for documents for one foi ministry request
        subquery_maxversion = _session.query(Document.documentid, func.max(Document.version).label('max_version')).group_by(Document.documentid).subquery()
        joincondition_maxversion = [
            subquery_maxversion.c.documentid == Document.documentid,
            subquery_maxversion.c.max_version == Document.version,
        ]

        selectedcolumns = [
            Document.documentid,
            Document.version,
            Document.filename,
            Document.filepath,
            Document.attributes,
            Document.foiministryrequestid,
            Document.createdby,
            Document.created_at,
            Document.updatedby,
            Document.updated_at,
            Document.statusid,
            DocumentStatus.name.label('status'),
            DocumentTag.tag.label('tags')
        ]

        query = _session.query(
                                *selectedcolumns
                            ).join(
                                subquery_maxversion,
                                and_(*joincondition_maxversion)
                            ).join(
                                DocumentStatus,
                                DocumentStatus.statusid == Document.statusid
                            ).join(
                                DocumentTag,
                                and_(DocumentTag.documentid == Document.documentid, DocumentTag.documentversion == Document.version)
                            ).filter(Document.foiministryrequestid == foiministryrequestid).all()
        documents = []
        # document_schema = DocumentSchema(many=False)
        for row in query:
            # print(row)
            # row.created_at = pstformat(row.created_at)
            document = cls.__preparedocument(row, pstformat(row.created_at), pstformat(row.updated_at))
            documents.append(document)
        print(documents)
        return documents

    @classmethod
    def getdocument(cls, documentid):
        document_schema = DocumentSchema(many=False)
        query = db.session.query(Document).filter_by(documentid=documentid).order_by(Document.version.desc()).first()
        return document_schema.dump(query)

    def __preparedocument(document, created_at, updated_at):
        return {
            'documentid': document.documentid,
            'version': document.version,
            'filename': document.filename,
            'filepath': document.filepath,
            'attributes': document.attributes,
            'foiministryrequestid': document.foiministryrequestid,
            'createdby': document.createdby,            
            'created_at': created_at,
            'updatedby': document.updatedby,
            'updated_at': updated_at,
            'statusid': document.statusid,
            'status': document.status,
            'tags': document.tags
        }

class DocumentSchema(ma.Schema):
    class Meta:
        fields = ('documentid', 'version', 'filename', 'filepath', 'attributes', 'foiministryrequestid', 'createdby', 'created_at', 'updatedby', 'updated_at', 'statusid', 'documentstatus.name')