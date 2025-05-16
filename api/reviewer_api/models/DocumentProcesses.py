from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import and_
import logging

class DocumentProcesses(db.Model):
    __tablename__ = 'DocumentProcesses' 
    # Defining the columns
    processid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), unique=False, nullable=False)
    description = db.Column(db.Text, unique=False, nullable=False)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)

    @classmethod
    def getdocumentprocessbyid(cls, processid):
        try:
            documentstatus_schema = DocumentProcessesSchema(many=False)
            query = db.session.query(DocumentProcesses).filter_by(and_(processid = processid, isactive = True)).first()
            return documentstatus_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
    
    @classmethod
    def getdocumentprocessbyname(cls, name):
        try:
            documentstatus_schema = DocumentProcessesSchema(many=False)
            query = db.session.query(DocumentProcesses).filter_by(and_(name = name, isactive = True)).first()
            return documentstatus_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

class DocumentProcessesSchema(ma.Schema):
    class Meta:
        fields = ('processid', 'name', 'description', 'isactive')