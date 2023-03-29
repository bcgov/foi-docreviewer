from .db import  db, ma
from datetime import datetime as datetime2
from sqlalchemy.dialects.postgresql import JSON
from .default_method_result import DefaultMethodResult


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
        db.session.add(row)
        db.session.commit()
        return DefaultMethodResult(True,'PDF Stitch Job recorded for ministryrequestid: {0}'.format(row.ministryrequestid), row.pdfstitchjobid)

    @classmethod
    def getpdfstitchjobstatus(cls, requestid, category):
        pdfstitchjobschema = PDFStitchJobSchema(many=False)
        query = db.session.query(PDFStitchJob).filter(PDFStitchJob.ministryrequestid == requestid, PDFStitchJob.category == category.lower()).order_by(PDFStitchJob.pdfstitchjobid.desc(), PDFStitchJob.version.desc()).first()
        return pdfstitchjobschema.dump(query)
class PDFStitchJobSchema(ma.Schema):
    class Meta:
        fields = ('pdfstitchjobid', 'version', 'ministryrequestid', 'category', 'inputfiles', 'outputfiles', 'status', 'message', 'createdat', 'createdby')