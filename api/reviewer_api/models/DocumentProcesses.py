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
            query = db.session.query(DocumentProcesses).filter(and_(DocumentProcesses.processid == processid, DocumentProcesses.isactive == True)).first()
            return documentstatus_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
    
    @classmethod
    def getdocumentprocessidbyname(cls, name):
        try:
            query_result = db.session.query(DocumentProcesses).filter(
                and_(DocumentProcesses.name == name, DocumentProcesses.isactive == True)
            ).first()
            return query_result.processid if query_result else None
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()

class DocumentProcessesSchema(ma.Schema):
    class Meta:
        fields = ('processid', 'name', 'description', 'isactive')