from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult

class DocumentDeleted(db.Model):
    __tablename__ = 'DocumentDeleted'
    # Defining the columns
    documentdeletedid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filepath = db.Column(db.String(500), nullable=False)
    deleted = db.Column(db.Boolean, unique=False, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    updatedby = db.Column(db.String(120), unique=False, nullable=True)

    @classmethod
    def create(cls, rows):
        db.session.add_all(rows)
        db.session.commit()
        return DefaultMethodResult(True,'Deleted Row(s) Added', -1, [{"id": row.documentdeletedid, "filepath": row.filepath} for row in rows]) 

class DocumentDeletedSchema(ma.Schema):
    class Meta:
        fields = ('documentdeletedid', 'filepath', 'created_at')