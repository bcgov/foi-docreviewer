from .db import  db, ma
from datetime import datetime as datetime2
from .default_method_result import DefaultMethodResult
from sqlalchemy import text
import logging

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


    @classmethod 
    def getdocumentmaster(cls, ministryrequestid):
        documentmasters = []
        try:
            sql = """select recordid, parentid, filepath, dm.documentmasterid, da."attributes", 
                    dm.created_at, dm.createdby  from "DocumentMaster" dm, "DocumentAttributes" da  
                    where dm.documentmasterid = da.documentmasterid 
                    and dm.ministryrequestid = :ministryrequestid"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                documentmasters.append({"recordid": row["recordid"], "parentid": row["parentid"], "filepath": row["filepath"], "documentmasterid": row["documentmasterid"], "attributes": row["attributes"],  "created_at": row["created_at"],  "createdby": row["createdby"]})
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return documentmasters
    
    @classmethod 
    def getdeleted(cls, ministryrequestid):
        documentmasters = []
        try:
            """
            
            sql = select distinct d.documentmasterid  
                        from "DocumentMaster" d , "DocumentDeleted" dd where  d.filepath like dd.filepath||'%' 
                  and d.ministryrequestid =:ministryrequestid
            """
            
            sql = """select distinct d.documentmasterid  
                        from "DocumentMaster" d , "DocumentDeleted" dd where  d.filepath like dd.filepath||'%' 
                        and d.ministryrequestid = dd.ministryrequestid and d.ministryrequestid =:ministryrequestid"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                documentmasters.append(row["documentmasterid"])
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return documentmasters

    
    
    @classmethod 
    def getredactionready(cls, ministryrequestid, deleted):
        documentmasters = []
        try:
            sql = """select documentmasterid, processingparentid, isredactionready, parentid  
                        from "DocumentMaster" dm where dm.ministryrequestid = :ministryrequestid 
                        and isredactionready = true;"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                if row["processingparentid"] not in deleted:
                    documentmasters.append({"documentmasterid": row["documentmasterid"], "processingparentid": row["processingparentid"], "isredactionready": row["isredactionready"], "parentid": row["parentid"]})
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return documentmasters
    
    @classmethod 
    def getdocumentproperty(cls, ministryrequestid, deleted):
        documentmasters = []
        try:
            sql = """select dm.documentmasterid,  dm.processingparentid, d.documentid, 
                        dhc.rank1hash, d.filename, d.pagecount, dm.parentid from "DocumentMaster" dm, 
                        "Documents" d, "DocumentHashCodes" dhc  
                        where dm.ministryrequestid = :ministryrequestid and dm.ministryrequestid  = d.foiministryrequestid   
                        and dm.documentmasterid = d.documentmasterid 
                        and d.documentid = dhc.documentid;"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                if (row["processingparentid"] is not None and row["processingparentid"] not in deleted) or (row["processingparentid"] is None and row["documentmasterid"] not in deleted):
                    documentmasters.append({"documentmasterid": row["documentmasterid"], "processingparentid": row["processingparentid"], "documentid": row["documentid"], "rank1hash": row["rank1hash"], "filename": row["filename"], "pagecount": row["pagecount"], "parentid": row["parentid"]})
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return documentmasters

class DeduplicationJobSchema(ma.Schema):
    class Meta:
        fields = ('documentmasterid', 'filepath', 'ministryrequestid', 'recordid', 'processingparentid', 'parentid', 'isredactionready', 'created_at', 'createdby', 'updated_at', 'updatedby')