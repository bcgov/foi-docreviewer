from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import and_

class DocumentStatus(db.Model):
    __tablename__ = 'DocumentStatus' 
    # Defining the columns
    statusid = db.Column(db.Integer, primary_key=True,autoincrement=True)
    name = db.Column(db.String(120), unique=False, nullable=False)
    description = db.Column(db.Text, unique=False, nullable=False)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)

    @classmethod
    def getdocumentstatus(cls, statusid):
        documentstatus_schema = DocumentStatusSchema(many=True)
        query = db.session.query(DocumentStatus).filter_by(and_(statusid = statusid, isactive = True)).first()
        return documentstatus_schema.dump(query)

class DocumentStatusSchema(ma.Schema):
    class Meta:
        fields = ('statusid', 'name', 'description','isactive')