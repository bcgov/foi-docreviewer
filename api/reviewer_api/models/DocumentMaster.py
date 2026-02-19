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
    def get_converted_references(cls, ministryrequestid: int, recordgroups: list[int]):
        """
        Finds the output metadata for records that are being converted or have 
        completed conversion, including in-progress conversions.
        """
        sql = """
            SELECT 
                dm.recordid,
                dm.parentid,
                COALESCE(d.filename, dm.attachmentof) AS attachmentof,
                dm.filepath,
                dm.compressedfilepath,
                dm.ocrfilepath,
                dm.documentmasterid,
                da."attributes",
                dm.created_at,
                dm.createdby,
                dm.processingparentid,
                dm.isredactionready,
                dm.updated_at,
                NULL AS duplicate_of 
            FROM "DocumentMaster" dm
            LEFT JOIN "Documents" d 
                ON d.documentmasterid = dm.documentmasterid
            LEFT JOIN "DocumentAttributes" da 
                ON da.documentmasterid = dm.documentmasterid AND da.isactive = true
            WHERE dm.processingparentid IN (
                SELECT documentmasterid 
                FROM "DocumentMaster" 
                WHERE recordid = ANY(:recordgroups)
                AND ministryrequestid = :ministryrequestid
            )
            AND dm.ministryrequestid = :ministryrequestid
            ORDER BY dm.created_at;
        """
        params = {
            "ministryrequestid": ministryrequestid,
            "recordgroups": recordgroups
        }

        return sql, params

    @classmethod
    def build_non_document_set_query(cls,
            ministryrequestid: int,
            only_redaction_ready: bool = True,
    ):
        sql = """
              SELECT dm.recordid, \
                     dm.parentid, \
                     d.filename AS attachmentof, \
                     dm.filepath, \
                     dm.compressedfilepath, \
                     dm.ocrfilepath, \
                     dm.documentmasterid, \
                     da."attributes", \
                     dm.created_at, \
                     dm.createdby, \
                     dm.processingparentid, \
                     dm.isredactionready, \
                     dm.updated_at, \
                     NULL AS duplicate_of
              FROM "DocumentMaster" dm
                       JOIN "DocumentAttributes" da
                            ON da.documentmasterid = dm.documentmasterid
                                AND da.isactive = true
                       LEFT JOIN "DocumentMaster" dm2
                                 ON dm2.processingparentid = dm.parentid
                                     AND dm2.createdby = 'conversionservice'
                       LEFT JOIN "Documents" d
                                 ON d.documentmasterid = dm2.documentmasterid
              WHERE dm.ministryrequestid = :ministryrequestid \
              """

        params = {
            "ministryrequestid": ministryrequestid,
        }

        if only_redaction_ready:
            sql += "\n  AND dm.isredactionready = true"

        sql += """
        ORDER BY
            da.attributes ->> 'lastmodified' DESC,
            da.attributeid ASC
        """

        return sql, params

    @staticmethod
    def safe_row_value(row, key):
        """Safely get a value from a SQLAlchemy Row object, returning None if the key doesn't exist."""
        try:
            return row[key]
        except (KeyError, AttributeError):
            return None

    @classmethod
    def _process_row_to_dict(cls, row):
        """Convert a SQLAlchemy Row object to a dictionary."""
        return {
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
            "attachmentof": cls.safe_row_value(row, "attachmentof"),
            "duplicate_of": cls.safe_row_value(row, "duplicate_of"),
        }

    @classmethod
    def getdocumentmaster(cls, ministryrequestid):
        documentmasters = []
        
        sql, params = cls.build_non_document_set_query(
            ministryrequestid=ministryrequestid,
            only_redaction_ready=False,
        )

        try:
            rs = db.session.execute(text(sql), params)

            for row in rs:
                documentmasters.append(cls._process_row_to_dict(row))

        except Exception:
            logging.exception("Failed to fetch DocumentMaster")
            raise
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

    @classmethod
    def get_distinct_divisions_by_record(cls, ministryrequestid, recordids):
        """
        Returns distinct divisions (JSON shape preserved) per recordid,
        based on documents sharing the same filename.
        """
        try:
            sql = text("""
                    WITH target_records AS (
                        SELECT
                            dm.recordid,
                            d.filename
                        FROM "DocumentMaster" dm
                        JOIN "Documents" d
                            ON d.documentmasterid = dm.documentmasterid
                        WHERE dm.ministryrequestid = :ministryrequestid
                          AND dm.recordid = ANY(:recordids)
                    ),
                    distinct_divisions AS (
                        SELECT DISTINCT
                            tr.recordid,
                            (div->>'divisionid')::int AS divisionid
                        FROM target_records tr
                        JOIN "Documents" d2
                            ON d2.filename = tr.filename
                        JOIN "DocumentMaster" dm2
                            ON dm2.documentmasterid = d2.documentmasterid
                        JOIN "DocumentAttributes" da
                            ON da.documentmasterid = dm2.documentmasterid
                        CROSS JOIN LATERAL jsonb_array_elements(
                            (da.attributes->'divisions')::jsonb
                        ) AS div
                        WHERE dm2.ministryrequestid = :ministryrequestid
                          AND da.isactive = true
                          AND div->>'divisionid' IS NOT NULL
                    )
                    SELECT
                        recordid,
                        jsonb_build_object(
                            'divisions',
                            jsonb_agg(
                                jsonb_build_object('divisionid', divisionid)
                                ORDER BY divisionid
                            )
                        ) AS divisions
                    FROM distinct_divisions
                    GROUP BY recordid
                    ORDER BY recordid;
                """)

            result = db.session.execute(
                sql,
                {
                    "ministryrequestid": ministryrequestid,
                    "recordids": recordids
                }
            )

            return result.fetchall()

        except Exception as ex:
            logging.error("Error retrieving divisions by recordid", exc_info=ex)
            raise

        finally:
            db.session.close()
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