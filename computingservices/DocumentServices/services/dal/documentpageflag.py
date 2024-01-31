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
                where isactive = true order by sortorder
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
    def getsections_by_documentid_pageno(cls, ministryrequestid, redactionlayerid, documentid, pagenos):
        conn = getdbconnection()
        sections = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """select a.pagenumber, as2."section"  from "AnnotationSections" as2,
                    "Annotations" a
                    where as2.foiministryrequestid = %s::integer
                    and as2.isactive = true
                    and as2.annotationname  = a.annotationname 
                    and as2.redactionlayerid = a.redactionlayerid 
                    and a.redactionlayerid = %s::integer 
                    and a.documentid =  %s::integer
                    and a.pagenumber in %s
                    order by a.pagenumber;""",
                (ministryrequestid, redactionlayerid, documentid, tuple(pagenos)),
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