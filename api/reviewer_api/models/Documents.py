from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime as datetime2
from sqlalchemy.orm import relationship, backref, aliased
from sqlalchemy import func, case
from .DocumentStatus import DocumentStatus
from .DocumentDeleted import DocumentDeleted
from .DocumentTags import DocumentTag
from .DocumentHashCodes import DocumentHashCodes
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
    pagecount = db.Column(db.Integer, nullable=True)
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
            DocumentTag.tag.label('tags'),
            Document.pagecount
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
                            ).join(
                                DocumentDeleted,
                                DocumentDeleted.filepath == Document.filepath, isouter=True
                            ).filter(
                                Document.foiministryrequestid == foiministryrequestid,
                                DocumentDeleted.deleted == False or DocumentDeleted.deleted == None
                            ).all()
        documents = []
        for row in query:
            document = cls.__preparedocument(row, pstformat(row.created_at), pstformat(row.updated_at))
            documents.append(document)
        return documents

    @classmethod
    def getdocument(cls, documentid):
        document_schema = DocumentSchema(many=False)
        query = db.session.query(Document).filter_by(documentid=documentid).order_by(Document.version.desc()).first()
        return document_schema.dump(query)

    @classmethod
    def getdocumentsdedupestatus(cls, requestid):
        sq = db.session.query(
            func.min(DocumentHashCodes.documentid).label('minid')
        ).join(
            Document, Document.documentid == DocumentHashCodes.documentid
        ).join(
            DocumentDeleted, Document.filepath.contains(DocumentDeleted.filepath), isouter=True
        ).filter(
            Document.foiministryrequestid == requestid,
            DocumentDeleted.deleted == False or DocumentDeleted.deleted == None
        ).group_by(DocumentHashCodes.rank1hash).subquery('sq')
        sq2 = db.session.query(
            func.min(DocumentHashCodes.documentid).label('minid'), DocumentHashCodes.rank1hash
        ).join(
            Document, Document.documentid == DocumentHashCodes.documentid
        ).join(
            DocumentDeleted, Document.filepath.contains(DocumentDeleted.filepath), isouter=True
        ).filter(
            Document.foiministryrequestid == requestid,
            DocumentDeleted.deleted == False or DocumentDeleted.deleted == None
        ).group_by(DocumentHashCodes.rank1hash).subquery('sq2')

        xpr = case([(sq.c.minid != None, False),],
        else_ = True).label("isduplicate")
        originaldocument = aliased(Document)
        selectedcolumns = [
            xpr,
            originaldocument.filename.label('duplicateof'),
            originaldocument.filepath.label('duplicatefilepath'),
            Document.documentid,
            Document.version,
            Document.filename,
            Document.filepath,
            Document.foiministryrequestid,
            Document.createdby,
            Document.created_at,
            Document.updatedby,
            Document.updated_at,
            DocumentTag.tag.label('attributes'),
            DocumentTag.tag['isattachment'].astext.cast(db.Boolean).label('isattachment'),
            DocumentHashCodes.rank1hash.label('rank1hash'),
            DocumentHashCodes.rank2hash.label('rank2hash'),
            Document.pagecount
        ]
        query = db.session.query(*selectedcolumns).filter(
            Document.foiministryrequestid == requestid,
            DocumentDeleted.deleted == False or DocumentDeleted.deleted == None
        ).join(
            DocumentDeleted, Document.filepath.contains(DocumentDeleted.filepath), isouter=True
        ).join(
            sq, sq.c.minid == Document.documentid, isouter=True
        ).join(
            DocumentTag, Document.documentid == DocumentTag.documentid
        ).join(
            DocumentHashCodes, Document.documentid == DocumentHashCodes.documentid
        ).join(
            sq2, sq2.c.rank1hash == DocumentHashCodes.rank1hash
        ).join(
            originaldocument, originaldocument.documentid == sq2.c.minid
        ).order_by(DocumentHashCodes.created_at.asc()).all()
        return [r._asdict() for r in query]

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
            'lastmodified': updated_at,
            'statusid': document.statusid,
            'status': document.status,
            'divisions': document.tags['divisions'],
            'pagecount': document.pagecount
        }

class DocumentSchema(ma.Schema):
    class Meta:
        fields = ('documentid', 'version', 'filename', 'filepath', 'attributes', 'foiministryrequestid', 'createdby', 'created_at', 'updatedby', 'updated_at', 'statusid', 'documentstatus.name', 'pagecount')