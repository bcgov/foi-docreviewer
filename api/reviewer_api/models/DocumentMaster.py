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
    compressedfilepath = db.Column(db.String(500), nullable=True)
    ocrfilepath = db.Column(db.String(500), nullable=True)

    @classmethod
    def create(cls, row):
        try:
            db.session.add(row)
            db.session.commit()
            return DefaultMethodResult(True,'Document(s) Added: {0}'.format(row.filepath), row.documentmasterid)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod 
    def getdocumentmaster(cls, ministryrequestid, recordgroups=None):

        if recordgroups is None:
            recordgroups = []

        documentmasters = []
        try:
            sql = """
                select
                    dm.recordid,
                    dm.parentid,
                    d.filename as attachmentof,
                    dm.filepath,
                    dm.compressedfilepath,
                    dm.ocrfilepath,
                    dm.documentmasterid,
                    da."attributes",
                    dm.created_at,
                    dm.createdby,
                    dm.processingparentid as processingparentid,
                    dm.isredactionready as isredactionready,
                    dm.updated_at
                from "DocumentMaster" dm
                join "DocumentAttributes" da
                    on dm.documentmasterid = da.documentmasterid
                left join "DocumentMaster" dm2
                    on dm2.processingparentid = dm.parentid
                    and dm2.createdby = 'conversionservice'
                left join "Documents" d
                    on dm2.documentmasterid = d.documentmasterid
                where dm.ministryrequestid = :ministryrequestid
                and da.isactive = true
                and dm.documentmasterid not in (
                    select distinct d.documentmasterid
                    from "DocumentMaster" d
                    join "DocumentDeleted" dd
                        on d.filepath like dd.filepath || '%'
                    where d.ministryrequestid = :ministryrequestid
                )
            """

            params = {"ministryrequestid": ministryrequestid}

            if recordgroups:
                sql += """
                and dm.recordid = ANY(:recordgroups)
                """
                params["recordgroups"] = recordgroups

            rs = db.session.execute(text(sql), params)
            for row in rs:
                # if row["documentmasterid"] not in deleted:
                documentmasters.append({
                    "recordid": row["recordid"],
                    "parentid": row["parentid"],
                    "filepath": row["filepath"],
                    "compressedfilepath": row["compressedfilepath"],
                    "ocrfilepath": row["ocrfilepath"],
                    "documentmasterid": row["documentmasterid"],
                    "attributes": row["attributes"],
                    "created_at": row["created_at"],
                     "createdby": row["createdby"],
                    "processingparentid": row["processingparentid"],
                    "isredactionready": row["isredactionready"],
                    "updated_at": row["updated_at"],
                    "attachmentof": row["attachmentof"],
                })

        except Exception as ex:
            logging.error(ex)
            db.session.close()
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
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return documentmasters
    

    @classmethod
    def getprocessingchilddocumentids(cls, documentmasterids):
        documentmasters = []
        try:
            sql = """select d.documentid
                    from public."DocumentMaster" dm
                    left join public."Documents" d on d.documentmasterid = dm.documentmasterid
                    where processingparentid = :documentmasterids or dm.documentmasterid = :documentmasterids"""
            rs = db.session.execute(text(sql), {'documentmasterids': documentmasterids})
            for row in rs:
                documentmasters.append(row["documentid"])
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return documentmasters

    
    @classmethod 
    def filterreplacednoconversionfiles(cls, ministryrequestid):
        documentmasters = []
        try:
            # filter out replaced jpg, png & pdf files - files do not need conversion
            sql = """select processingparentid
						from "DocumentMaster"
						where processingparentid is not Null and ministryrequestid =:ministryrequestid"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                documentmasters.append(row["processingparentid"])
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return documentmasters

    @classmethod 
    def filterreplacedfiles(cls, ministryrequestid):
        documentmasters = []
        try:
            # all original/replaced other type of files + all original/replaced (jpg, png & pdf) files
            sql = """select MAX(documentmasterid) as documentmasterid
						from public."DocumentMaster"
						where processingparentid is not null and ministryrequestid =:ministryrequestid
						group by processingparentid"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                documentmasters.append(row["documentmasterid"])
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return documentmasters

    @classmethod 
    def filteroriginalnoconversionfiles(cls, ministryrequestid):
        documentmasters = []
        try:
            # all original/replaced other type of files + all original/replaced (jpg, png & pdf) files
            sql = """select documentmasterid
						from public."DocumentMaster"
						where processingparentid is null and ministryrequestid =:ministryrequestid"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                documentmasters.append(row["documentmasterid"])
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return documentmasters
    

    # @classmethod
    # def getfilepathbydocumentidold(cls, documentid):
    #     try:
    #         sql = """select dm.filepath
    #                 from public."DocumentMaster" dm
    #                 join public."Documents" d on d.documentmasterid = dm.documentmasterid
    #                 where d.documentid = :documentid"""
    #         rs = db.session.execute(text(sql), {'documentid': documentid}).first()
    #     except Exception as ex:
    #         logging.error(ex)
    #         db.session.close()
    #         raise ex
    #     finally:
    #         db.session.close()
    #     return rs[0]

    @classmethod
    def getfilepathbydocumentid(cls, documentid):
        try:
            result= {}
            sql = """SELECT 
                        dm.filepath as filepath,
                        d.selectedfileprocessversion as selectedfileprocessversion,
                        CASE 
                            WHEN dm.processingparentid IS NOT NULL THEN parent_dm.compressedfilepath
                            ELSE dm.compressedfilepath
                        END AS compressedfilepath,
                        CASE 
                            WHEN dm.processingparentid IS NOT NULL THEN parent_dm.ocrfilepath
                            ELSE dm.ocrfilepath
                        END AS ocrfilepath
                    FROM public."DocumentMaster" dm
                    JOIN public."Documents" d ON d.documentmasterid = dm.documentmasterid
                    LEFT JOIN public."DocumentMaster" parent_dm ON dm.processingparentid = parent_dm.documentmasterid
                    WHERE d.documentid = :documentid
                """
            rs = db.session.execute(text(sql), {'documentid': documentid}).first()
            result=  {
                "filepath": rs[0],
                "selectedfileprocessversion": rs[1],
                "compressedfilepath": rs[2],
                "ocrfilepath": rs[3],
            }
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return result
        #return rs[0]
    
    @classmethod 
    def getredactionready(cls, ministryrequestid):
        documentmasters = []
        try:
            sql = """select documentmasterid, processingparentid, isredactionready, parentid
                        from "DocumentMaster" dm where dm.ministryrequestid = :ministryrequestid
                        and isredactionready = true and (processingparentid not in (select distinct d.documentmasterid
                        from "DocumentMaster" d , "DocumentDeleted" dd where  d.filepath like dd.filepath||'%'
                        and d.ministryrequestid = dd.ministryrequestid and d.ministryrequestid =:ministryrequestid) or processingparentid is null);"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                # if row["processingparentid"] not in deleted:
                documentmasters.append({"documentmasterid": row["documentmasterid"], "processingparentid": row["processingparentid"], "isredactionready": row["isredactionready"], "parentid": row["parentid"]})
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return documentmasters
    
    @classmethod 
    def getdocumentproperty(cls, ministryrequestid, deleted):
        documentmasters = []
        try:
            sql = """select dm.documentmasterid,  dm.processingparentid, dm.createdby as createdby, d.documentid, d.version,
                        dhc.rank1hash, d.filename, d.originalpagecount, d.pagecount, dm.parentid, d.selectedfileprocessversion
                        from "DocumentMaster" dm, 
                        "Documents" d, "DocumentHashCodes" dhc  
                        where dm.ministryrequestid = :ministryrequestid and dm.ministryrequestid  = d.foiministryrequestid   
                        and dm.documentmasterid = d.documentmasterid 
                        and d.documentid = dhc.documentid order by dm.documentmasterid;"""
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            for row in rs:
                if (row["processingparentid"] is not None and row["processingparentid"] not in deleted) or (row["processingparentid"] is None and row["documentmasterid"] not in deleted):
                    documentmasters.append({"documentmasterid": row["documentmasterid"], "processingparentid": row["processingparentid"],"createdby": row["createdby"] ,
                                            "documentid": row["documentid"], "rank1hash": row["rank1hash"], "filename": row["filename"], "originalpagecount": row["originalpagecount"],
                                            "pagecount": row["pagecount"], "parentid": row["parentid"], "version": row["version"],
                                            "selectedfileprocessversion": row["selectedfileprocessversion"],})
        except Exception as ex:
            logging.error(ex)
            db.session.close()
            raise ex
        finally:
            db.session.close()
        return documentmasters
    

    @classmethod
    def updateredactionstatus(cls, documentmasterid, userid):
        try:
            sql =   """ update "DocumentMaster"
                        set isredactionready= false, updatedby  = :userid, updated_at = now()
                        where documentmasterid = :documentmasterid
                    """
            db.session.execute(text(sql), {'userid': userid, 'documentmasterid': documentmasterid})
            db.session.commit()
            print("Redaction status updated")
            return DefaultMethodResult(True,'Redactionready status updated for document master id:', -1, [{"id": documentmasterid}])
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
class DeduplicationJobSchema(ma.Schema):
    class Meta:
        fields = ('documentmasterid', 'filepath', 'ministryrequestid', 'recordid', 'processingparentid', 'parentid', 'isredactionready', 
                  'created_at', 'createdby', 'updated_at', 'updatedby','compressedfilepath','ocrfilepath')