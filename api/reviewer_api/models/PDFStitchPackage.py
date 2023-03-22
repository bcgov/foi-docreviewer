from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult


class PDFStitchPackage(db.Model):
    __tablename__ = 'PDFStitchPackage'
    # Defining the columns
    pdfstitchpackageid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    finalpackagepath = db.Column(db.String(500), primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)    
    created_at = db.Column(db.DateTime, default=datetime2.now)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    

    @classmethod
    def create(cls, row):
        db.session.add(row)
        db.session.commit()
        return DefaultMethodResult(True,'Final package path Added: {0}'.format(row.finalpackagepath), row.pdfstitchpackageid)


class PDFStitchPackageMasterSchema(ma.Schema):
    class Meta:
        fields = ('pdfstitchpackageid', 'finalpackagepath', 'ministryrequestid', 'category', 'created_at', 'createdby')