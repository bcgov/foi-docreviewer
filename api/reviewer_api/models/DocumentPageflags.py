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
from sqlalchemy.orm import relationship, backref
from reviewer_api.models.DocumentPageflagHistory import DocumentPageflagHistory
import json

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
    redactionlayerid = db.Column(db.Integer, db.ForeignKey('RedactionLayers.redactionlayerid'))
    # redactionlayer = relationship("RedactionLayer", backref=backref("RedactionLayers"), uselist=False)

    @classmethod
    def createpageflag(cls, _foiministryrequestid, _documentid, _documentversion, _pageflag, userinfo, redactionlayerid, _pageattributes=None)->DefaultMethodResult:
        try:
            db.session.add(DocumentPageflag(foiministryrequestid=_foiministryrequestid,
                                            documentid = _documentid,
                                            documentversion = _documentversion,
                                            pageflag = _pageflag,
                                            attributes = _pageattributes,
                                            createdby = userinfo,
                                            created_at = datetime.now(),
                                            redactionlayerid = redactionlayerid
                                            ))
            db.session.commit()
            return DefaultMethodResult(True, 'Page Flag is saved', _documentid)  
        except Exception as ex:
            logging.error(ex)
            return DefaultMethodResult(True, 'Page Flag is not saved', _documentid) 
        finally:
            db.session.close()

    @classmethod
    def savepageflag(cls, _foiministryrequestid, _documentid, _documentversion, _pageflag, userinfo, redactionlayerid, _pageattributes=None)->DefaultMethodResult:
        try:
            dbquery = db.session.query(DocumentPageflag)
            pageflag = dbquery.filter(and_(DocumentPageflag.foiministryrequestid == _foiministryrequestid,DocumentPageflag.documentid == _documentid, DocumentPageflag.documentversion == _documentversion, DocumentPageflag.redactionlayerid == redactionlayerid))
            if(pageflag.count() == 1) :
                pageflagobj = pageflag.first()
                DocumentPageflagHistory.createpageflag(DocumentPageflagHistory(
                    documentpageflagid=pageflagobj.id,
                    foiministryrequestid=pageflagobj.foiministryrequestid,
                    documentid = pageflagobj.documentid,
                    documentversion = pageflagobj.documentversion,
                    pageflag = json.dumps(pageflagobj.pageflag),
                    attributes = json.dumps(pageflagobj.attributes),
                    createdby = json.dumps(pageflagobj.createdby),
                    created_at = pageflagobj.created_at,
                    updatedby = json.dumps(pageflagobj.updatedby),
                    updated_at = pageflagobj.updated_at,
                    redactionlayerid = pageflagobj.redactionlayerid
                ))
                pageflag.update({
                    DocumentPageflag.pageflag:_pageflag,
                    DocumentPageflag.attributes:_pageattributes,
                    DocumentPageflag.updated_at:datetime.now(),
                    DocumentPageflag.updatedby:userinfo
                }, synchronize_session = False)
                db.session.commit()
                return DefaultMethodResult(True,'Page Flag is saved', _documentid)
            elif(pageflag.count() == 0):
                return cls.createpageflag(_foiministryrequestid, _documentid, _documentversion, _pageflag, userinfo, redactionlayerid, _pageattributes)
            raise Exception('More than 1 pageflag row created for layerid: ' + redactionlayerid)
        except Exception as ex:
            logging.error(ex)
            return DefaultMethodResult(True, 'Page Flag is not saved', _documentid)
        finally:
            db.session.close()

    @classmethod
    def getpageflag(cls,  _foiministryrequestid, _documentid, _documentversion, _redactionlayerid):
        try:
            pageflag_schema = DocumentPageflagSchema(many=False)
            query = db.session.query(DocumentPageflag).filter(and_(
                DocumentPageflag.foiministryrequestid == _foiministryrequestid,
                DocumentPageflag.documentid == _documentid,
                DocumentPageflag.documentversion == _documentversion,
                DocumentPageflag.redactionlayerid.in_(_redactionlayerid)
            )).order_by(DocumentPageflag.id.desc(), DocumentPageflag.documentversion.desc()).first()
            return pageflag_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
    
    @classmethod
    def getpageflag_by_request(cls,  _foiministryrequestid, redactionlayerid):
        pageflags = []
        try:              
            sql = """select distinct on (dp.documentid) dp.documentid, dp.documentversion, dp.pageflag
                     from "DocumentPageflags" dp
                     join "Documents" d on dp.documentid = d.documentid
                     join "DocumentMaster" dm on dm.documentmasterid = d.documentmasterid
                     left join "DocumentDeleted" dd on dm.filepath ilike dd.filepath || '%'
                     where dp.foiministryrequestid = :foiministryrequestid and (dd.deleted is false or dd.deleted is null)
                     and redactionlayerid in :redactionlayerid
                     order by dp.documentid, dp.documentversion desc;
                    """
            rs = db.session.execute(text(sql), {'foiministryrequestid': _foiministryrequestid, 'redactionlayerid': tuple(redactionlayerid)})
        
            for row in rs:
                pageflags.append({"documentid":row["documentid"],"documentversion":row["documentversion"],"pageflag":row["pageflag"]})
        except Exception as ex:
            logging.error(ex)
            db.session.close()
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
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return pageflags

class DocumentPageflagSchema(ma.Schema):
    class Meta:
        fields = ('id', 'foiministryrequestid', 'documentid','documentversion','pageflag','attributes','createdby','created_at','updatedby','updated_at', 'redactionlayerid')