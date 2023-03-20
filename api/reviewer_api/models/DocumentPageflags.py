from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_
from datetime import datetime as datetime2
from sqlalchemy.sql.schema import ForeignKey, ForeignKeyConstraint
import logging
from sqlalchemy.dialects.postgresql import JSON, insert
from datetime import datetime
from sqlalchemy import or_, and_
from sqlalchemy import text

class DocumentPageflag(db.Model):
  
    __tablename__ = 'DocumentPageflags' 
    constraint_pg = db.Index("constraint_pg", 'foiministryrequestid', 'documentid','documentversion')
    # Defining the columns
    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    foiministryrequestid = db.Column(db.Integer, nullable=False)
    documentid = db.Column(db.Integer, ForeignKey('Documents.documentid')) 
    documentversion = db.Column(db.Integer, ForeignKey('Documents.version')) 
    pageflag = db.Column(db.Text, unique=False, nullable=False)  
    attributes = db.Column(db.Text, unique=False, nullable=True)  
    createdby = db.Column(db.Text, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(db.Text, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def createpageflag(cls, _foiministryrequestid, _documentid, _documentversion, _pageflag, userinfo)->DefaultMethodResult:
        try:
            db.session.add(DocumentPageflag(foiministryrequestid=_foiministryrequestid,
                                            documentid = _documentid,
                                            documentversion = _documentversion,
                                            pageflag = _pageflag,
                                            createdby = userinfo,
                                            created_at = datetime.now()
                                            ))
            db.session.commit()
            return DefaultMethodResult(True, 'Page Flag is saved', _documentid)  
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()

    @classmethod
    def updatepageflag(cls, _foiministryrequestid, _documentid, _documentversion, _pageflag, userinfo)->DefaultMethodResult:
        try:
            dbquery = db.session.query(DocumentPageflag)
            pageflag = dbquery.filter(and_(DocumentPageflag.foiministryrequestid == _foiministryrequestid,DocumentPageflag.documentid == _documentid, DocumentPageflag.documentversion == _documentversion))
            if(pageflag.count() > 0) :
                pageflag.update({DocumentPageflag.pageflag:_pageflag, DocumentPageflag.updated_at:datetime.now(), DocumentPageflag.updatedby:userinfo}, synchronize_session = False)
                db.session.commit()
                return DefaultMethodResult(True,'Page Flag is saved', _documentid)
            else:
                return DefaultMethodResult(False,'Page Flag does not exists',-1)   
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()

    @classmethod
    def savepublicbody(cls, _foiministryrequestid, _documentid, _documentversion, _attributes, userinfo)->DefaultMethodResult:
        try:
            dbquery = db.session.query(DocumentPageflag)
            pageflag = dbquery.filter(and_(DocumentPageflag.foiministryrequestid == _foiministryrequestid,DocumentPageflag.documentid == _documentid, DocumentPageflag.documentversion == _documentversion))
            if(pageflag.count() > 0) :
                pageflag.update({DocumentPageflag.attributes:_attributes, DocumentPageflag.updated_at:datetime.now(), DocumentPageflag.updatedby:userinfo}, synchronize_session = False)
                db.session.commit()
                return DefaultMethodResult(True,'Public body is saved', _documentid)
            else:
                return DefaultMethodResult(False,'Public body does not exists',-1)   
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
    
    @classmethod
    def getpageflag(cls,  _foiministryrequestid, _documentid, _documentversion):
        pageflag_schema = DocumentPageflagSchema(many=False)
        query = db.session.query(DocumentPageflag).filter(and_(DocumentPageflag.foiministryrequestid == _foiministryrequestid,DocumentPageflag.documentid == _documentid, DocumentPageflag.documentversion == _documentversion)).one_or_none()
        return pageflag_schema.dump(query)
    
    @classmethod
    def getpageflag_by_request(cls,  _foiministryrequestid):
        pageflags = []
        try:              
            sql = """select distinct on (documentid) documentid, documentversion, pageflag from "DocumentPageflags" dp  
                    where foiministryrequestid = :foiministryrequestid order by documentid, documentversion desc;
                    """
            rs = db.session.execute(text(sql), {'foiministryrequestid': _foiministryrequestid})
        
            for row in rs:
                pageflags.append({"documentid":row["documentid"],"documentversion":row["documentversion"],"pageflag":row["pageflag"]})
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return pageflags
    
    @classmethod
    def getpublicbody_by_request(cls,  _foiministryrequestid):
        pageflags = []
        try:              
            sql = """select distinct on (documentid) documentid, attributes from "DocumentPageflags" dp  
                    where foiministryrequestid = :foiministryrequestid order by documentid, documentversion desc;
                    """
            rs = db.session.execute(text(sql), {'foiministryrequestid': _foiministryrequestid})
        
            for row in rs:
                pageflags.append({"documentid":row["documentid"],"attributes":row["attributes"]})
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return pageflags

class DocumentPageflagSchema(ma.Schema):
    class Meta:
        fields = ('id', 'foiministryrequestid', 'documentid','documentversion','pageflag','attributes','createdby','created_at','updatedby','updated_at')