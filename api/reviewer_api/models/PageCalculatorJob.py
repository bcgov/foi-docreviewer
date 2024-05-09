from .db import db, ma
from datetime import datetime as datetime2
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import func, and_
from .default_method_result import DefaultMethodResult
import logging


class PageCalculatorJob(db.Model):
    __tablename__ = "PageCalculatorJob"
    # Defining the columns
    pagecalculatorjobid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)
    inputmessage = db.Column(JSON, nullable=False)
    pagecount = db.Column(JSON, nullable=True)
    status = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)
    createdat = db.Column(db.DateTime, default=datetime2.now, nullable=False)
    createdby = db.Column(db.String(120), nullable=False)

    @classmethod
    def insert(cls, row):
        try:
            db.session.add(row)
            db.session.commit()
            return DefaultMethodResult(
                True,
                "PageCalculatorJob recorded for ministryrequestid: {0}".format(
                    row.ministryrequestid
                ),
                row.pagecalculatorjobid,
            )
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

class PageCalculatorJobSchema(ma.Schema):
    class Meta:
        fields = (
            "pagecalculatorjobid",
            "version",
            "ministryrequestid",
            "inputmessage",
            "pagecount",
            "status",
            "message",
            "createdat",
            "createdby",
        )
