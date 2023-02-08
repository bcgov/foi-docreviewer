from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult
from sqlalchemy import text

class DocumentMaster(db.Model):
    __tablename__ = 'DocumentMaster'
    # Defining the columns
    documentmasterid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filepath = db.Column(db.String(500), primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)
    recordid = db.Column(db.Integer, nullable=True)
    processingparentid = db.Column(db.Integer, nullable=True)
    parentid = db.Column(db.Integer, nullable=True)
    isredactionready = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    updatedby = db.Column(db.String(120), unique=False, nullable=True)

    @classmethod
    def create(cls, row):
        db.session.add(row)
        db.session.commit()
        return DefaultMethodResult(True,'Document(s) Added: {0}'.format(row.filepath), row.documentmasterid)


class DeduplicationJobSchema(ma.Schema):
    class Meta:
        fields = ('documentmasterid', 'filepath', 'ministryrequestid', 'recordid', 'processingparentid', 'parentid', 'isredactionready', 'created_at', 'createdby', 'updated_at', 'updatedby')