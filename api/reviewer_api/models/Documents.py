from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime as datetime2
from sqlalchemy.orm import relationship, backref, aliased
from sqlalchemy import func, case
from .DocumentStatus import DocumentStatus
from .DocumentDeleted import DocumentDeleted
from .DocumentAttributes import DocumentAttributes
from .DocumentHashCodes import DocumentHashCodes
from .DocumentMaster import DocumentMaster
from .FileConversionJob import FileConversionJob
from .DeduplicationJob import DeduplicationJob
from reviewer_api.utils.util import pstformat
import json
import logging

class Document(db.Model):
    __tablename__ = 'Documents' 
    # Defining the columns
    documentid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    filename = db.Column(db.String(120), unique=False, nullable=False)
    documentmasterid = db.Column(db.Integer, db.ForeignKey('DocumentMaster.documentmasterid'), unique=False, nullable=False)
    attributes = db.Column(JSON, unique=False, nullable=True)
    foiministryrequestid = db.Column(db.Integer, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(JSON, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    statusid = db.Column(db.Integer, db.ForeignKey('DocumentStatus.statusid'))
    pagecount = db.Column(db.Integer, nullable=True)
    incompatible = db.Column(db.Boolean, nullable=True)
    documentstatus = relationship("DocumentStatus", backref=backref("DocumentStatus"), uselist=False)
    documentmaster = relationship("DocumentMaster", backref=backref("DocumentMaster"), uselist=False)

    @classmethod
    def getdocuments(cls, foiministryrequestid):
        try:
            _session = db.session

            #subquery for getting latest version for documents for one foi ministry request
            subquery_maxversion = _session.query(Document.documentid, func.max(Document.version).label('max_version')).group_by(Document.documentid).subquery()
            joincondition_maxversion = [
                subquery_maxversion.c.documentid == Document.documentid,
                subquery_maxversion.c.max_version == Document.version,
            ]

            #subquery for filtering out duplicates, merging divisions
            subquery_hashcode = cls.__getcompatableoriginalsubquery(foiministryrequestid).add_columns(
                func.json_agg(DocumentAttributes.attributes['divisions'][0]).label('divisions'),
            ).join(
                DocumentAttributes, case(
                    [(DocumentMaster.processingparentid == None, DocumentMaster.documentmasterid == DocumentAttributes.documentmasterid),],
                    else_ = DocumentMaster.processingparentid == DocumentAttributes.documentmasterid
                )
            ).subquery('sq')

            selectedcolumns = [
                Document.documentid,
                Document.version,
                Document.filename,
                DocumentMaster.filepath,
                Document.attributes,
                Document.foiministryrequestid,
                Document.createdby,
                Document.created_at,
                Document.updatedby,
                Document.updated_at,
                Document.statusid,           
                DocumentStatus.name.label('status'),
                (func.to_jsonb(DocumentAttributes.attributes).op('||')(func.jsonb_build_object('divisions', subquery_hashcode.c.divisions))).label('attributes'),
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
                                    subquery_hashcode,
                                    subquery_hashcode.c.minid == Document.documentid
                                ).join(
                                    DocumentMaster,
                                    DocumentMaster.documentmasterid == Document.documentmasterid
                                ).join(
                                    DocumentAttributes, case(
                                        [(DocumentMaster.processingparentid == None, DocumentMaster.documentmasterid == DocumentAttributes.documentmasterid),],
                                        else_ = DocumentMaster.processingparentid == DocumentAttributes.documentmasterid
                                    )
                                ).filter(
                                    Document.foiministryrequestid == foiministryrequestid
                                    
                                ).all()
            documents = []
            for row in query:
                document = cls.__preparedocument(row, pstformat(row.created_at), pstformat(row.updated_at))
                documents.append(document)
            return documents
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        
    @classmethod
    def getdocument(cls, documentid):
        try:
            document_schema = DocumentSchema(many=False)
            query = db.session.query(Document).filter_by(documentid=documentid).order_by(Document.version.desc()).first()
            document = document_schema.dump(query)
            document['filepath'] = document['documentmaster.filepath']
            del document['documentmaster.filepath']
            return document
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()

    @classmethod
    def getdocumentsbyids(cls, idlist):
        try:
            _session = db.session

            #subquery for getting latest version for documents for one foi ministry request
            subquery_maxversion = _session.query(Document.documentid, func.max(Document.version).label('max_version')).group_by(Document.documentid).subquery()
            joincondition_maxversion = [
                subquery_maxversion.c.documentid == Document.documentid,
                subquery_maxversion.c.max_version == Document.version,
            ]

            selectedcolumns = [
                Document.documentid,
                DocumentMaster.filepath
            ]

            query = _session.query(
                                    *selectedcolumns
                                ).join(
                                    subquery_maxversion,
                                    and_(*joincondition_maxversion)
                                ).join(
                                    DocumentMaster,
                                    DocumentMaster.documentmasterid == Document.documentmasterid
                                ).filter(
                                    Document.documentid.in_(idlist)
                                ).all()

            documents = {
                row.documentid: row.filepath
                for row in query
            }
            return documents
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()

    @classmethod
    def getdocumentsdedupestatus(cls, requestid):
        try:
            sq = cls.__getoriginalsubquery(requestid).add_columns(
                func.min(DocumentMaster.processingparentid).label('processingparentid'),
                func.min(DocumentMaster.documentmasterid).label('minmasterid')
            ).subquery('sq')
            sq2 = cls.__getoriginalsubquery(requestid).add_columns(
                func.min(DocumentMaster.processingparentid).label('processingparentid'),
                func.min(DocumentMaster.documentmasterid).label('minmasterid')
            ).subquery('sq2')
            sq3 = db.session.query(
                Document.documentid,
                Document.filename,
                Document.pagecount,
                DocumentMaster.documentmasterid,
                DocumentMaster.processingparentid,
                DocumentMaster.createdby,
                DocumentMaster.isredactionready
            ).join(
                DocumentMaster, Document.documentmasterid == DocumentMaster.documentmasterid
            ).join(
                DocumentDeleted, DocumentMaster.filepath.contains(DocumentDeleted.filepath), isouter=True
            ).filter(
                Document.foiministryrequestid == requestid,
                DocumentDeleted.deleted == False or DocumentDeleted.deleted == None,
            ).subquery('sq3')

            xpr = case([(and_(sq.c.minid == None, sq3.c.documentid != None), True),],
            else_ = False).label("isduplicate")
            filename = case([
                (FileConversionJob.status != 'completed', FileConversionJob.filename),
                (DeduplicationJob.status != 'completed', DeduplicationJob.filename)
                ], else_ = sq3.c.filename).label("filename")
            originaldocument = aliased(Document)
            originaldocumentmaster = aliased(DocumentMaster)
            selectedcolumns = [
                xpr,
                originaldocument.filename.label('duplicateof'),
                originaldocumentmaster.documentmasterid.label('duplicatemasterid'),
                DocumentMaster.documentmasterid,
                DocumentMaster.recordid,
                DocumentMaster.parentid,
                DocumentMaster.filepath,
                FileConversionJob.status.label('conversionstatus'),
                FileConversionJob.outputdocumentmasterid,
                DeduplicationJob.status.label('deduplicationstatus'),
                DeduplicationJob.trigger,
                filename,
                DocumentMaster.ministryrequestid,
                DocumentMaster.createdby,
                DocumentMaster.created_at,
                DocumentMaster.updatedby,
                DocumentMaster.updated_at,
                DocumentAttributes.attributes,
                DocumentAttributes.attributes['isattachment'].astext.cast(db.Boolean).label('isattachment'),
                sq3.c.pagecount,
                sq3.c.isredactionready
            ]
            query = db.session.query(*selectedcolumns).select_from(DocumentMaster).filter(
                DocumentMaster.ministryrequestid == requestid,
                DocumentMaster.processingparentid == None,
                DocumentDeleted.deleted == False or DocumentDeleted.deleted == None,
            ).join(
                sq3, case(
                    [(sq3.c.processingparentid == None, sq3.c.documentmasterid == DocumentMaster.documentmasterid),],
                    else_ = sq3.c.processingparentid == DocumentMaster.documentmasterid
                ), isouter=True
            ).join(
                DocumentDeleted, DocumentMaster.filepath.contains(DocumentDeleted.filepath), isouter=True
            )

            sqfc = db.session.query(
                func.max(FileConversionJob.createdat)
            ).filter(FileConversionJob.inputdocumentmasterid == DocumentMaster.documentmasterid).correlate(DocumentMaster)

            query = query.join(
                FileConversionJob, and_(
                    FileConversionJob.createdat == sqfc.as_scalar(),
                    FileConversionJob.inputdocumentmasterid == DocumentMaster.documentmasterid
                ), isouter=True
            )

            sqd = db.session.query(
                func.max(DeduplicationJob.createdat)
            ).filter(case(
                [(and_(sq3.c.processingparentid != None, sq3.c.createdby != 'conversionservice'), sq3.c.documentmasterid == DeduplicationJob.documentmasterid),],
                else_ = DocumentMaster.documentmasterid == DeduplicationJob.documentmasterid
            )).correlate(DocumentMaster, sq3)

            query = query.join(
                DeduplicationJob, and_(
                    DeduplicationJob.createdat == sqd.as_scalar()
                ), isouter=True
            ).join(
                sq, case(
                    [(sq.c.processingparentid == None, sq.c.minmasterid == DocumentMaster.documentmasterid),],
                    else_ = sq.c.processingparentid == DocumentMaster.documentmasterid
                ), isouter=True
            ).join(
                DocumentAttributes, DocumentMaster.documentmasterid == DocumentAttributes.documentmasterid, isouter=True
            ).join(
                DocumentHashCodes, sq3.c.documentid == DocumentHashCodes.documentid, isouter=True
            ).join(
                sq2, sq2.c.rank1hash == DocumentHashCodes.rank1hash, isouter=True
            ).join(
                originaldocument, originaldocument.documentid == sq2.c.minid, isouter=True
            ).join(
                originaldocumentmaster, case(
                    [(sq2.c.processingparentid == None, sq2.c.minmasterid == originaldocumentmaster.documentmasterid),],
                    else_ = sq2.c.processingparentid == originaldocumentmaster.documentmasterid
                ), isouter=True
            ).order_by(DocumentHashCodes.created_at.asc()).all()
            return [r._asdict() for r in query]
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        
    @classmethod
    def __preparedocument(cls, document, created_at, updated_at):
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
            'divisions': document.attributes['divisions'],
            'pagecount': document.pagecount
        }

    # subquery to fetch the earliest uploaded, non-deleted duplicates in a request
    @classmethod
    def __getoriginalsubquery(cls, requestid):
        try:
            return db.session.query(
                func.min(DocumentHashCodes.documentid).label('minid'), DocumentHashCodes.rank1hash
            ).join(
                Document, Document.documentid == DocumentHashCodes.documentid
            ).join(
                DocumentMaster, Document.documentmasterid == DocumentMaster.documentmasterid
            ).join(
                DocumentDeleted, DocumentMaster.filepath.contains(DocumentDeleted.filepath), isouter=True
            ).filter(
                Document.foiministryrequestid == requestid,
                DocumentDeleted.deleted == False or DocumentDeleted.deleted == None
                
            ).group_by(DocumentHashCodes.rank1hash)
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
    
    # subquery to fetch the earliest uploaded, non-deleted duplicates AND incompatable FALSE in a request
    @classmethod
    def __getcompatableoriginalsubquery(cls, requestid):
        try:
            return db.session.query(
                func.min(DocumentHashCodes.documentid).label('minid'), DocumentHashCodes.rank1hash
            ).join(
                Document, Document.documentid == DocumentHashCodes.documentid and Document.foiministryrequestid == requestid
            ).join(
                DocumentMaster, Document.documentmasterid == DocumentMaster.documentmasterid and DocumentMaster.ministryrequestid == requestid
            ).join(
                DocumentDeleted, DocumentMaster.filepath.contains(DocumentDeleted.filepath) and DocumentDeleted.ministryrequestid == requestid, isouter=True
            ).filter(
                Document.foiministryrequestid == requestid,
                DocumentDeleted.deleted == False or DocumentDeleted.deleted == None,
                Document.incompatible == False
            ).group_by(DocumentHashCodes.rank1hash)
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()

class DocumentSchema(ma.Schema):
    class Meta:
        fields = ('documentid', 'version', 'filename', 'documentmaster.filepath', 'attributes', 'foiministryrequestid', 'createdby', 'created_at', 'updatedby', 'updated_at', 'statusid', 'documentstatus.name', 'pagecount')