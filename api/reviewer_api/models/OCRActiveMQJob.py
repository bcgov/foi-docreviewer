from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult
from sqlalchemy import text
import logging

class OCRActiveMQJob(db.Model):
    __tablename__ = 'OCRActiveMQJob'
    # Defining the columns
    ocractivemqjobid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)
    createdat = db.Column(db.DateTime, default=datetime2.now, nullable=False)
    batch = db.Column(db.String(120), nullable=False)
    trigger = db.Column(db.String(120), nullable=False)
    documentmasterid = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)

    @classmethod
    def insert(cls, row):
        try:
            db.session.add(row)
            db.session.commit()
            return DefaultMethodResult(True,'OCRActiveMQJob Job recorded for documentmaster id: {0}'.format(row.documentmasterid), row.ocractivemqjobid)
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        
    
    @classmethod 
    def getocractivemqstatus(cls, ministryrequestid):
        executions = []
        try:
            sql = """select distinct on (ocractivemqjobid) ocractivemqjobid, version, 
                        filename, status, documentmasterid, "trigger", message    
                        from "OCRActiveMQJob" where ministryrequestid = :ministryrequestid
                        order by ocractivemqjobid, "version" desc"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                executions.append({"ocractivemqjobid": row["ocractivemqjobid"], "version": row["version"], "filename": row["filename"], "status": row["status"], 
                                   "documentmasterid": row["documentmasterid"],  "trigger": row["trigger"],"message": row["message"]})
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return executions

class OCRActiveMQJobSchema(ma.Schema):
    class Meta:
        fields = ('ocractivemqjobid', 'version', 'ministryrequestid', 'createdat', 'batch', 'trigger', 'filename', 'status', 'message','documentmasterid')