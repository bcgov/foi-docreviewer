from utils import getdbconnection
import logging
import json

class documentpageflag:

    @classmethod
    def get_all_pageflags(cls):
        conn = getdbconnection()
        pageflags = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select pageflagid, name, description from "Pageflags" 
                where isactive = true and name not in ('Consult') order by sortorder
                """
            )

            result = cursor.fetchall()
            cursor.close()
            if result is not None:
                for entry in result:
                    pageflags.append({"pageflagid": entry[0], "name": entry[1], "description": entry[2]})
                return pageflags
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
        conn = getdbconnection()
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
                return programareas
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
                    documentpageflags[entry[0]] = {"pageflag": entry[2], "attributes": entry[3]}
                return documentpageflags
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
                return docids
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
                return docpgs
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
                return sections
            return None

        except Exception as error:
            logging.error("Error in getting sections for requestid")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()