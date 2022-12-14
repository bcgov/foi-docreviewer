from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult
from sqlalchemy import text

class DeduplicationJob(db.Model):
    __tablename__ = 'DeduplicationJob'
    # Defining the columns
    deduplicationjobid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)
    createdat = db.Column(db.DateTime, default=datetime2.now, nullable=False)
    batch = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    trigger = db.Column(db.String(120), nullable=False)
    filepath = db.Column(db.String(240), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)

    @classmethod
    def insert(cls, row):
        db.session.add(row)
        db.session.commit()
        return DefaultMethodResult(True,'Deduplication Job recorded for filepath: {0}'.format(row.filepath), row.deduplicationjobid)

    @classmethod
    def getfilesdeduped(cls, requestid):
        sql = """select  count(1)  as completed
                        FROM "DeduplicationJob" dj
                        left outer join "DocumentDeleted" dd on dj.filepath ilike dd.filepath || '%'
                        where status = 'completed' and ministryrequestid = :ministryrequestid and (deleted is false or deleted is null) """

        rs = db.session.execute(text(sql), {'ministryrequestid': requestid})
        completed = rs.fetchone()["completed"]

        sql = """select filepath, status from public."DeduplicationJob" dj
                join (select max(deduplicationjobid) from public."DeduplicationJob" fcj
                left outer join "DocumentDeleted" dd on fcj.filepath ilike dd.filepath || '%'
                where (deleted is false or deleted is null)
                group by fcj.filepath) sq on sq.max = dj.deduplicationjobid
                where status = 'error' and ministryrequestid = :ministryrequestid"""
        rs = db.session.execute(text(sql), {'ministryrequestid': requestid})
        error = []
        for row in rs:
            error.append(row["filepath"])

        return completed, error

class DeduplicationJobSchema(ma.Schema):
    class Meta:
        fields = ('deduplicationjobid', 'version', 'ministryrequestid', 'createdat', 'batch', 'trigger', 'filepath', 'filename', 'status', 'message')