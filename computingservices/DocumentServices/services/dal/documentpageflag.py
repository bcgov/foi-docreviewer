from utils import getdbconnection, getfoidbconnection
import logging
import json
import time

class documentpageflag:

    @staticmethod
    def __resolve_connection(connection_factory, conn=None):
        if conn is not None:
            return conn, False
        return connection_factory(), True

    @classmethod
    def get_all_pageflags(cls, ignoreflags, conn=None):
        start_time = time.time()
        conn, should_close_conn = cls.__resolve_connection(getdbconnection, conn)
        pageflags = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select pageflagid, name, description from "Pageflags" 
                where isactive = true order by sortorder;"""               
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    if entry[1] not in ignoreflags:
                        pageflags.append({"pageflagid": entry[0], "name": entry[1], "description": entry[2]})
                logging.info(f"[PERF] DAL get_all_pageflags elapsed={time.time() - start_time:.3f}s")
                return pageflags
            logging.info(f"[PERF] DAL get_all_pageflags elapsed={time.time() - start_time:.3f}s")
            return None

        except Exception as error:
            logging.error("Error in getting page flags")
            logging.error(error)
            raise
        finally:
            if should_close_conn and conn is not None:
                conn.close()

    @classmethod
    def get_all_programareas(cls, conn=None):
        start_time = time.time()
        conn, should_close_conn = cls.__resolve_connection(getfoidbconnection, conn)
        programareas = {}
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select programareaid, bcgovcode, iaocode from "ProgramAreas" 
                where isactive = true order by programareaid
                """
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    programareas[entry[0]] = {"bcgovcode": entry[1], "iaocode": entry[2]}
                logging.info(f"[PERF] DAL get_all_programareas elapsed={time.time() - start_time:.3f}s")
                return programareas
            logging.info(f"[PERF] DAL get_all_programareas elapsed={time.time() - start_time:.3f}s")
            return None

        except Exception as error:
            logging.error("Error in getting program areas")
            logging.error(error)
            raise
        finally:
            if should_close_conn and conn is not None:
                conn.close()

    @classmethod
    def get_documentpageflag(cls, ministryrequestid, redactionlayerid, documentids, conn=None):
        start_time = time.time()
        conn, should_close_conn = cls.__resolve_connection(getdbconnection, conn)
        documentpageflags = {}
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select documentid, documentversion, pageflag, attributes 
                from "DocumentPageflags" dp where 
                foiministryrequestid = %s::integer and redactionlayerid = %s::integer and documentid in %s
                order by documentid ;""",
                (ministryrequestid, redactionlayerid, tuple(documentids)),
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    sortedpageflags = sorted(entry[2], key=lambda x: x["page"]) 
                    documentpageflags[entry[0]] = {"pageflag": sortedpageflags , "attributes": entry[3]}
                logging.info(f"[PERF] DAL get_documentpageflag request={ministryrequestid} docs={len(documentids)} elapsed={time.time() - start_time:.3f}s")
                return documentpageflags
            logging.info(f"[PERF] DAL get_documentpageflag request={ministryrequestid} docs={len(documentids)} elapsed={time.time() - start_time:.3f}s")
            return None

        except Exception as error:
            logging.error("Error in getting document page flags")
            logging.error(error)
            raise
        finally:
            if should_close_conn and conn is not None:
                conn.close()

    @classmethod
    def get_documents_lastmodified(cls, ministryrequestid, documentids):
        start_time = time.time()
        conn = getdbconnection()
        docids = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select d.documentid  from "Documents" d join "DocumentMaster" dm on d.foiministryrequestid = dm.ministryrequestid and d.documentmasterid = dm.documentmasterid 
                    join "DocumentAttributes" da on (da.documentmasterid = d.documentmasterid or da.documentmasterid = dm.processingparentid) 
                    where documentid in %s
                    and d.foiministryrequestid = %s::integer
                    group by d.documentid, da."attributes" ->> 'lastmodified' ::text
                    order by da."attributes" ->> 'lastmodified'""",
                (tuple(documentids),ministryrequestid),
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    docids.append(entry[0])
                logging.info(f"[PERF] DAL get_documents_lastmodified request={ministryrequestid} docs={len(documentids)} elapsed={time.time() - start_time:.3f}s")
                return docids
            logging.info(f"[PERF] DAL get_documents_lastmodified request={ministryrequestid} docs={len(documentids)} elapsed={time.time() - start_time:.3f}s")
            return None

        except Exception as error:
            logging.error("Error in getting documentids for requestid")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()


    @classmethod
    def getpagecount_by_documentid(cls, ministryrequestid, documentids, conn=None):
        start_time = time.time()
        conn, should_close_conn = cls.__resolve_connection(getdbconnection, conn)
        docpgs = {}
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select documentid, pagecount  from "Documents" d 
                where foiministryrequestid = %s::integer  
                and documentid in %s;""",
                (ministryrequestid, tuple(documentids)),
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    docpgs[entry[0]] = {"pagecount": entry[1]}
                logging.info(f"[PERF] DAL getpagecount_by_documentid request={ministryrequestid} docs={len(documentids)} elapsed={time.time() - start_time:.3f}s")
                return docpgs
            logging.info(f"[PERF] DAL getpagecount_by_documentid request={ministryrequestid} docs={len(documentids)} elapsed={time.time() - start_time:.3f}s")
            return None

        except Exception as error:
            logging.error("Error in getting pagecount for requestid")
            logging.error(error)
            raise
        finally:
            if should_close_conn and conn is not None:
                conn.close()
    
    @classmethod
    def getoriginalpagecount_by_documentid(cls, ministryrequestid, documentids, conn=None):
        start_time = time.time()
        conn, should_close_conn = cls.__resolve_connection(getdbconnection, conn)
        docpgs = {}
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select documentid, originalpagecount  from "Documents" d 
                where foiministryrequestid = %s::integer  
                and documentid in %s;""",
                (ministryrequestid, tuple(documentids)),
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    docpgs[entry[0]] = {"pagecount": entry[1]}
                logging.info(f"[PERF] DAL getoriginalpagecount_by_documentid request={ministryrequestid} docs={len(documentids)} elapsed={time.time() - start_time:.3f}s")
                return docpgs
            logging.info(f"[PERF] DAL getoriginalpagecount_by_documentid request={ministryrequestid} docs={len(documentids)} elapsed={time.time() - start_time:.3f}s")
            return None

        except Exception as error:
            logging.error("Error in getting pagecount for requestid")
            logging.error(error)
            raise
        finally:
            if should_close_conn and conn is not None:
                conn.close()

    @classmethod
    def getsections_by_documentid_pageno(cls, redactionlayerid, documentid, pagenos, conn=None):
        start_time = time.time()
        conn, should_close_conn = cls.__resolve_connection(getdbconnection, conn)
        sections = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select pagenumber , unnest(xpath('//contents/text()', annotation::xml))::text as sections 
                   from "Annotations" a 
                   where annotation like '%%freetext%%' and isactive = true 
                   and redactionlayerid = %s::integer
                   and documentid = %s::integer
                   and pagenumber in %s
                   order by pagenumber;""",
                (redactionlayerid, documentid, tuple(pagenos)),
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    sections.append({"pageno": entry[0], "section": entry[1]})
                logging.info(f"[PERF] DAL getsections_by_documentid_pageno layer={redactionlayerid} doc={documentid} pages={len(pagenos)} elapsed={time.time() - start_time:.3f}s")
                return sections
            logging.info(f"[PERF] DAL getsections_by_documentid_pageno layer={redactionlayerid} doc={documentid} pages={len(pagenos)} elapsed={time.time() - start_time:.3f}s")
            return None

        except Exception as error:
            logging.error("Error in getting sections for requestid")
            logging.error(error)
            raise
        finally:
            if should_close_conn and conn is not None:
                conn.close()

    @classmethod
    def getsections_batch(cls, redactionlayerid, document_pages, conn=None):
        start_time = time.time()
        if not document_pages:
            return []

        requested_pairs = [
            (int(documentid), int(pageno))
            for documentid, pagenos in document_pages.items()
            for pageno in sorted(set(pagenos))
        ]
        if not requested_pairs:
            return []

        conn, should_close_conn = cls.__resolve_connection(getdbconnection, conn)
        sections = []
        try:
            cursor = conn.cursor()
            documentids = [pair[0] for pair in requested_pairs]
            pagenumbers = [pair[1] for pair in requested_pairs]
            cursor.execute(
                """
                WITH requested_pages AS (
                    SELECT *
                    FROM unnest(%s::integer[], %s::integer[]) AS rp(documentid, pagenumber)
                )
                SELECT a.documentid,
                       a.pagenumber,
                       unnest(xpath('//contents/text()', a.annotation::xml))::text AS sections
                FROM "Annotations" a
                JOIN requested_pages rp
                  ON rp.documentid = a.documentid
                 AND rp.pagenumber = a.pagenumber
                WHERE a.isactive = true
                  AND a.redactionlayerid = %s::integer
                  AND a.annotationtype = 'freetext'
                ORDER BY a.documentid, a.pagenumber;
                """,
                (documentids, pagenumbers, redactionlayerid),
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    sections.append({"documentid": entry[0], "pageno": entry[1], "section": entry[2]})
            logging.info(
                f"[PERF] DAL getsections_batch layer={redactionlayerid} docs={len(document_pages)} "
                f"pages={len(requested_pairs)} elapsed={time.time() - start_time:.3f}s"
            )
            return sections

        except Exception as error:
            logging.error("Error in getting batched sections for requestid")
            logging.error(error)
            raise
        finally:
            if should_close_conn and conn is not None:
                conn.close()

    @classmethod
    def getdeletedpages(cls, ministryrequestid, docids, conn=None):
        start_time = time.time()
        conn, should_close_conn = cls.__resolve_connection(getdbconnection, conn)
        deldocpages = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select id, documentid, pagemetadata  
                from "DocumentDeletedPages" 
                where ministryrequestid = %s::integer and documentid in  %s
                order by documentid, id;""",
                (ministryrequestid, tuple(docids)),
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    deldocpages.append({"id": entry[0], "documentid": entry[1], "pagemetadata": entry[2]})
                logging.info(f"[PERF] DAL getdeletedpages request={ministryrequestid} docs={len(docids)} elapsed={time.time() - start_time:.3f}s")
                return deldocpages
            logging.info(f"[PERF] DAL getdeletedpages request={ministryrequestid} docs={len(docids)} elapsed={time.time() - start_time:.3f}s")
            return None
        except Exception as error:
            logging.error("Error in getting deletedpages for requestid")
            logging.error(error)
            raise
        finally:
            if should_close_conn and conn is not None:
                conn.close()

    @classmethod
    def getrecentredactionlayerid(cls, ministryrequestid, conn=None):
        start_time = time.time()
        conn, should_close_conn = cls.__resolve_connection(getdbconnection, conn)
        layerid = 1
        cursor = None
        try:
            cursor = conn.cursor()
            query = '''
                select redactionlayerid  
                from "DocumentPageflags" 
                where foiministryrequestid = %s::integer
                and redactionlayerid NOT IN (select redactionlayerid from "RedactionLayers" where name in ('Response Package', 'Open Info'))
                --openinfo layer is excluded latest redaction layer because it always uses the normal redaction summary & 
                --exclude response package from layer query in document services disable context menu to prevent page flags from being created for response package
                order by created_at, id desc limit 1;
            '''
            cursor.execute(query, (ministryrequestid,))
            layerid = cursor.fetchone()
            logging.info(f"[PERF] DAL getrecentredactionlayerid request={ministryrequestid} elapsed={time.time() - start_time:.3f}s")
            return layerid
        except Exception as error:
            logging.error("Error in getting recentredactionlayerid for requestid")
            logging.error(error)
        finally:
            if cursor is not None:
                cursor.close()
            if should_close_conn and conn is not None:
                conn.close()
