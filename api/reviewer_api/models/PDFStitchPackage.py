from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult
from sqlalchemy import func, text
import logging

class PDFStitchPackage(db.Model):
    __tablename__ = 'PDFStitchPackage'
    # Defining the columns
    pdfstitchpackageid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    finalpackagepath = db.Column(db.String(500), primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)    
    createdat = db.Column(db.DateTime, default=datetime2.now)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    

    @classmethod
    def create(cls, row):
        try:
            db.session.add(row)
            db.session.commit()
            return DefaultMethodResult(True,'Final package path Added: {0}'.format(row.finalpackagepath), row.pdfstitchpackageid)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
        
    @classmethod
    def getpdfstitchpackage(cls, requestid, category):
        try:
            pdfstitchpackageschema = PDFStitchPackageSchema(many=False)
            query = db.session.query(PDFStitchPackage).filter(PDFStitchPackage.ministryrequestid == requestid, PDFStitchPackage.category == category).order_by(PDFStitchPackage.pdfstitchpackageid.desc()).first()
            return pdfstitchpackageschema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getpdfstitchpackages(cls, requestid, category):
        try:
            sql = """SELECT DISTINCT ON (category) * FROM public."PDFStitchPackage" 
            WHERE category LIKE :category AND ministryrequestid = :requestid 
            ORDER BY category, pdfstitchpackageid DESC;
            """
            res = db.session.execute(text(sql), {'category': category+'%', 'requestid': int(requestid)})
            pdfstitchjobpackages = [{'category': row['category'], 'pdfstitchpackageid': row['pdfstitchpackageid'], 'ministryrequestid': row['ministryrequestid'], 'finalpackagepath': row['finalpackagepath'], 'createdat': row['createdat']} for row in res]
            return pdfstitchjobpackages
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def isresponsepackagecreated(cls, requestid, generatedat):
        try:
            query = db.session.query(func.count(PDFStitchPackage.pdfstitchpackageid)).filter(PDFStitchPackage.ministryrequestid == requestid, PDFStitchPackage.category == "responsepackage", PDFStitchPackage.createdat <= generatedat)
            packagecount = query.scalar()
            return True if packagecount > 0 else False
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
            
class PDFStitchPackageSchema(ma.Schema):
    class Meta:
        fields = ('pdfstitchpackageid', 'finalpackagepath', 'ministryrequestid', 'category', 'createdat', 'createdby')