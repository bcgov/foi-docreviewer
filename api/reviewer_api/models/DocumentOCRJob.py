from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult
from sqlalchemy import text
import logging

class DocumentOCRJob(db.Model):
    __tablename__ = 'DocumentOCRJob'
    # Defining the columns
    ocrjobid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    documentid = db.Column(db.Integer, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)
    documentmasterid = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)
    createdat = db.Column(db.DateTime, default=datetime2.now, nullable=False)
    createdby = db.Column(db.Text, unique=False, nullable=True)


    # @classmethod
    # def insert(cls, row):
    #     try:
    #         db.session.add(row)
    #         db.session.commit()
    #         return DefaultMethodResult(True,'DocumentOCRJob Job recorded for documentmaster id: {0}'.format(row.documentid), row.ocrjobid)
    #     except Exception as ex:
    #         logging.error(ex)
    #         raise ex
    #     finally:
    #         db.session.close()
        
    
    @classmethod 
    def getazureocrjobstatus(cls, ministryrequestid):
        executions = []
        try:
            sql = """select distinct on (ocrjobid) ocrjobid, version, 
                        createdat, status, documentid, documentmasterid,message, createdby   
                        from "DocumentOCRJob" where ministryrequestid = :ministryrequestid
                        order by ocrjobid, "version" desc"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                executions.append({"ocrjobid": row["ocrjobid"], "version": row["version"], "createdat": row["createdat"], "status": row["status"], 
                                   "documentid": row["documentid"],"documentmasterid": row["documentmasterid"],"message": row["message"], "createdby": row["createdby"]})
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return executions

class OCRActiveMQJobSchema(ma.Schema):
    class Meta:
        fields = ('ocrjobid', 'version','documentid', 'ministryrequestid', 'documentmasterid', 'status', 'message','createdat', 'createdby')