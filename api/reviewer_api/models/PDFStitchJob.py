from .db import  db, ma
from datetime import datetime as datetime2
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import func, and_
from .default_method_result import DefaultMethodResult
from .DocumentDeleted import DocumentDeleted
from .DocumentMaster import DocumentMaster
import logging

class PDFStitchJob(db.Model):
    __tablename__ = 'PDFStitchJob'
    # Defining the columns
    pdfstitchjobid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)    
    category = db.Column(db.String(50), nullable=False)
    inputfiles = db.Column(JSON, nullable=False)
    outputfiles = db.Column(JSON, nullable=True)
    status = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)
    createdat = db.Column(db.DateTime, default=datetime2.now, nullable=False)
    createdby = db.Column(db.String(120), nullable=False)

    @classmethod
    def insert(cls, row):
        try:
            db.session.add(row)
            db.session.commit()
            return DefaultMethodResult(True,'PDF Stitch Job recorded for ministryrequestid: {0}'.format(row.ministryrequestid), row.pdfstitchjobid)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
        
    @classmethod
    def getpdfstitchjobstatus(cls, requestid, category):
        try:
            pdfstitchjobschema = PDFStitchJobSchema(many=False)
            query = db.session.query(PDFStitchJob).filter(PDFStitchJob.ministryrequestid == requestid, PDFStitchJob.category == category.lower()).order_by(PDFStitchJob.pdfstitchjobid.desc(), PDFStitchJob.version.desc()).first()
            return pdfstitchjobschema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getrecordschanged(cls, requestid, category, jobid):
        try:
            query1 = (
                db.session.query(
                    func.max(PDFStitchJob.pdfstitchjobid).label('pdfstitchjobid'),
                    func.max(PDFStitchJob.version).label('version')
                )
                .join(DocumentMaster, DocumentMaster.ministryrequestid == PDFStitchJob.ministryrequestid)
                .filter(
                    and_(
                        PDFStitchJob.ministryrequestid == requestid,
                        PDFStitchJob.pdfstitchjobid == jobid,
                        PDFStitchJob.category == category,
                        PDFStitchJob.status.in_(['completed', 'error']),
                        DocumentMaster.created_at > PDFStitchJob.createdat
                    )
                )
                .group_by(PDFStitchJob.ministryrequestid, PDFStitchJob.category)
            )   

            query2 = (
                db.session.query(
                    func.max(PDFStitchJob.pdfstitchjobid).label('pdfstitchjobid'),
                    func.max(PDFStitchJob.version).label('version')
                )
                .join(DocumentDeleted, DocumentDeleted.ministryrequestid == PDFStitchJob.ministryrequestid)
                .filter(
                    and_(
                        PDFStitchJob.ministryrequestid == requestid,
                        PDFStitchJob.pdfstitchjobid == jobid,
                        PDFStitchJob.category == category,
                        PDFStitchJob.status.in_(['completed', 'error']),
                        DocumentDeleted.created_at > PDFStitchJob.createdat
                    )
                )
                .group_by(PDFStitchJob.ministryrequestid, PDFStitchJob.category)
            )

            # Combine the two queries using union
            final_query = query1.union(query2)
            row = final_query.one_or_none()
            print("row = ", row)
            if row is not None and len(row) > 0:
                print("Query returned at least one row.")
                return {"recordchanged": True}
            else:
                print("Query returned no rows.")
                return {"recordchanged": False}
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()




class PDFStitchJobSchema(ma.Schema):
    class Meta:
        fields = ('pdfstitchjobid', 'version', 'ministryrequestid', 'category', 'inputfiles', 'outputfiles', 'status', 'message', 'createdat', 'createdby')