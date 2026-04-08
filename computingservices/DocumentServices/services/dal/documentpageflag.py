from utils import getdbconnection, getfoidbconnection
import logging
import json
import time

class documentpageflag:

    @classmethod
    def get_all_pageflags(cls, ignoreflags):
        start_time = time.time()
        conn = getdbconnection()
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
            if conn is not None:
                conn.close()

    @classmethod
    def get_all_programareas(cls):
        start_time = time.time()
        conn = getfoidbconnection()
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
            if conn is not None:
                conn.close()

    @classmethod
    def get_documentpageflag(cls, ministryrequestid, redactionlayerid, documentids):
        start_time = time.time()
        conn = getdbconnection()
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
            if conn is not None:
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
    def getpagecount_by_documentid(cls, ministryrequestid, documentids):
        start_time = time.time()
        conn = getdbconnection()
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
            if conn is not None:
                conn.close()
    
    @classmethod
    def getoriginalpagecount_by_documentid(cls, ministryrequestid, documentids):
        start_time = time.time()
        conn = getdbconnection()
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
            if conn is not None:
                conn.close()

    @classmethod
    def getsections_by_documentid_pageno(cls, redactionlayerid, documentid, pagenos):
        start_time = time.time()
        conn = getdbconnection()
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
            if conn is not None:
                conn.close()

    @classmethod
    def getdeletedpages(cls, ministryrequestid, docids):
        start_time = time.time()
        conn = getdbconnection()
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
            if conn is not None:
                conn.close()

    @classmethod
    def getrecentredactionlayerid(cls, ministryrequestid):
        start_time = time.time()
        conn = getdbconnection()
        layerid = 1
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
            cursor.close()
            if conn is not None:
                conn.close()
