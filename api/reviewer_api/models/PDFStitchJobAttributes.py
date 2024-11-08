from .db import db, ma
from datetime import datetime as datetime2
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import func, and_
from .default_method_result import DefaultMethodResult
from .DocumentDeleted import DocumentDeleted
from .DocumentMaster import DocumentMaster
import logging


class PDFStitchJobAttributes(db.Model):
    __tablename__ = "PDFStitchJobAttributes"
    # Defining the columns
    attributesid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pdfstitchjobid = db.Column(db.Integer, db.ForeignKey("PDFStitchJob.pdfstitchjobid"))
    version = db.Column(db.Integer, db.ForeignKey("PDFStitchJob.version"))
    ministryrequestid = db.Column(db.Integer, nullable=False)
    attributes = db.Column(JSON, unique=False, nullable=False)
    createdat = db.Column(db.DateTime, default=datetime2.now, nullable=False)
    createdby = db.Column(db.String(120), nullable=False)


    @classmethod
    def insert(cls, row):
        try:
            db.session.add(row)
            db.session.commit()
            return DefaultMethodResult(
                True,
                "PDF Stitch Job Attributes recorded for ministryrequestid: {0}".format(
                    row.ministryrequestid
                ),
                row.pdfstitchjobid,
            )
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getpdfstitchjobattributesbyid(cls, requestid):
        try:
            pdfstitchjobattributesschema = PDFStitchJobAttributesSchema(many=False)
            query = db.session.query(PDFStitchJobAttributes).filter(
                    PDFStitchJobAttributes.ministryrequestid == requestid
                ).first()
            return pdfstitchjobattributesschema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

   


class PDFStitchJobAttributesSchema(ma.Schema):
    class Meta:
        fields = (
            "attributesid",
            "pdfstitchjobid",
            "version",
            "ministryrequestid",
            "attributes",
            "createdat",
            "createdby",
        )
