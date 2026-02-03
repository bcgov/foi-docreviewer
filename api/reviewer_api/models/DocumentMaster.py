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

    @classmethod
    def build_document_set_query(cls,
            ministryrequestid: int,
            recordgroups: list[int] | None = None,
            only_redaction_ready: bool = True,
    ):
        recordgroups = recordgroups or []

        base_where = "WHERE dm.ministryrequestid = :ministryrequestid"
        if recordgroups:
            base_where += " AND dm.recordid = ANY(:recordgroups)"

        sql = f"""
        WITH RECURSIVE doc_tree AS (
            -- 1. Base Case: Get the requested records
            SELECT dm.documentmasterid,
                   dm.recordid,
                   dm.processingparentid,
                   dm.parentid,
                   ARRAY[dm.documentmasterid] AS path,
                   0 as depth
            FROM "DocumentMaster" dm
            {base_where}

            UNION ALL

            -- 2. Recursive Step: Get children
            SELECT child.documentmasterid,
                   child.recordid,
                   child.processingparentid,
                   child.parentid,
                   parent.path || child.documentmasterid,
                   parent.depth + 1
            FROM "DocumentMaster" child
            JOIN doc_tree parent
              ON (child.processingparentid = parent.documentmasterid
                  OR child.parentid = parent.documentmasterid)
            WHERE NOT (child.documentmasterid = ANY(parent.path))
        ),

        -- 3. Get filenames currently in the tree
        tree_files AS (
            SELECT DISTINCT d.filename, dt.depth
            FROM doc_tree dt
            JOIN "Documents" d ON d.documentmasterid = dt.documentmasterid
        ),

        -- 4. Gather ALL candidate versions (Tree + History)
        all_versions AS (
            SELECT dt.documentmasterid, tf.filename, dm.created_at
            FROM doc_tree dt
            JOIN "DocumentMaster" dm ON dm.documentmasterid = dt.documentmasterid
            JOIN "Documents" d ON d.documentmasterid = dm.documentmasterid
            JOIN tree_files tf ON tf.filename = d.filename

            UNION ALL

            SELECT fcj.documentmasterid, d.filename, fcj.createdat AS created_at
            FROM "DeduplicationJob" fcj
            JOIN "Documents" d ON d.documentmasterid = fcj.documentmasterid
            WHERE fcj.ministryrequestid = :ministryrequestid
              AND d.filename IN (SELECT filename FROM tree_files)
        ),

        -- 5. Pick ONLY the Oldest Version per Filename
        unique_oldest_map AS (
            SELECT DISTINCT ON (filename)
                documentmasterid,
                filename,
                created_at
            FROM all_versions
            ORDER BY filename, created_at ASC
        )

        -- 6. Final Selection
        SELECT dm.recordid,
               dm.parentid,
               map.filename AS attachmentof,
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
               COALESCE(tf.depth, 0) as depth,
               
               -- Shows which Original Record ID this row is replacing
               (
                   SELECT string_agg(dt.recordid::text, ', ')
                   FROM doc_tree dt
                   JOIN "Documents" d_orig ON d_orig.documentmasterid = dt.documentmasterid
                   WHERE d_orig.filename = map.filename
                     AND dt.documentmasterid != dm.documentmasterid
               ) AS duplicate_of
               
        FROM unique_oldest_map map
        JOIN "DocumentMaster" dm ON dm.documentmasterid = map.documentmasterid
        LEFT JOIN "DocumentAttributes" da
            ON da.documentmasterid = dm.documentmasterid
           AND da.isactive = true
        LEFT JOIN tree_files tf ON tf.filename = map.filename
        WHERE 1=1
        """

        if only_redaction_ready:
            sql += " AND dm.isredactionready = true"

        sql += """
          AND COALESCE((da."attributes"->>'incompatible')::boolean, false) = false
        ORDER BY depth, dm.created_at
        """

        params = {
            "ministryrequestid": ministryrequestid,
            "recordgroups": recordgroups,
        }

        return sql, params

    @staticmethod
    def safe_row_value(row, key):
        """Safely get a value from a SQLAlchemy Row object, returning None if the key doesn't exist."""
        try:
            return row[key]
        except (KeyError, AttributeError):
            return None

    @classmethod
    def getdocumentmaster(cls, ministryrequestid, recordgroups=None):

        # Normalize input
        recordgroups = recordgroups or []

        # Decision rule:
        # - No recordgroups  -> no document Set query
        # - With recordgroups -> recursive query
        use_recursive = bool(recordgroups)

        documentmasters = []

        if use_recursive:
            sql, params = cls.build_document_set_query(
                ministryrequestid=ministryrequestid,
                recordgroups=recordgroups,
                only_redaction_ready=True,
            )
        else:
            sql, params = cls.build_non_document_set_query(
                ministryrequestid=ministryrequestid,
                only_redaction_ready=True,
            )

        try:
            rs = db.session.execute(text(sql), params)

            for row in rs:
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
                    "attachmentof": cls.safe_row_value(row, "attachmentof"),
                    "duplicate_of": cls.safe_row_value(row, "duplicate_of"),
                })

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