from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult
from sqlalchemy import text
import logging

class FileConversionJob(db.Model):
    __tablename__ = 'FileConversionJob'
    # Defining the columns
    fileconversionjobid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)
    createdat = db.Column(db.DateTime, default=datetime2.now, nullable=False)
    batch = db.Column(db.String(120), nullable=False)
    trigger = db.Column(db.String(120), nullable=False)
    inputdocumentmasterid = db.Column(db.Integer, nullable=False)
    outputdocumentmasterid = db.Column(db.Integer, nullable=True)
    filename = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)

    @classmethod
    def insert(cls, row):
        try:
            db.session.add(row)
            db.session.commit()
            return DefaultMethodResult(True,'Conversion Job recorded for documentmaster id: {0}'.format(row.inputdocumentmasterid), row.fileconversionjobid)
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        
    @classmethod
    def getfilesconverted(cls, requestid):
        try:
            sql = """select  count(1)  as completed
                            FROM "FileConversionJob" fcj
                            left outer join "DocumentDeleted" dd on fcj.inputfilepath ilike dd.filepath || '%'
                            where status = 'completed' and ministryrequestid = :ministryrequestid and (deleted is false or deleted is null) """

            rs = db.session.execute(text(sql), {'ministryrequestid': requestid})
            completed = rs.fetchone()["completed"]

            sql = """select inputfilepath as filepath, status from public."FileConversionJob" dj
                    join (select max(fileconversionjobid) from public."FileConversionJob" fcj
                    left outer join "DocumentDeleted" dd on fcj.inputfilepath ilike dd.filepath || '%'
                    where (deleted is false or deleted is null)
                    group by inputfilepath) sq on sq.max = dj.fileconversionjobid
                    where status = 'error' and ministryrequestid = :ministryrequestid"""
            rs = db.session.execute(text(sql), {'ministryrequestid': requestid})
            error = []
            for row in rs:
                error.append(row["filepath"])

            return completed, error
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
    
    @classmethod 
    def getconversionstatus(cls, ministryrequestid):
        executions = []
        try:
            sql = """select distinct on (fileconversionjobid) fileconversionjobid, version, 
                        filename, status, inputdocumentmasterid, "trigger", outputdocumentmasterid    
                        from "FileConversionJob" fcj  where ministryrequestid = :ministryrequestid
                        order by fileconversionjobid, "version" desc"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                executions.append({"fileconversionjobid": row["fileconversionjobid"], "version": row["version"], "filename": row["filename"], "status": row["status"], "documentmasterid": row["inputdocumentmasterid"],  "trigger": row["trigger"], "outputdocumentmasterid": row["outputdocumentmasterid"]})
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return executions

class FileConversionJobSchema(ma.Schema):
    class Meta:
        fields = ('fileconversionjobid', 'version', 'ministryrequestid', 'createdat', 'batch', 'trigger', 'inputfilepath', 'outputfilepath', 'filename', 'status', 'parentfilepath', 'parentfilename', 'message')