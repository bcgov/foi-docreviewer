from utils import getdbconnection
import logging
import json


class documentservice:

    @classmethod 
    def getdeleteddocuments(cls, ministryrequestid):
        conn = getdbconnection()
        deleted = []
        try:
            cursor = conn.cursor()
            query = '''
                SELECT DISTINCT d.documentmasterid
                FROM "DocumentMaster" d
                INNER JOIN "DocumentDeleted" dd ON d.filepath LIKE dd.filepath || '%%'
                WHERE d.ministryrequestid = dd.ministryrequestid
                AND d.ministryrequestid = %s::integer
            '''
            parameters = (ministryrequestid,)
            cursor.execute(query, parameters)
            results = cursor.fetchall()
            for row in results:
                deleted.append(row[0])
            return deleted
        except Exception as error:
            logging.error("Error in getdeleteddocuments")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()
    
    @classmethod
    def getdocumentmaster(cls, ministryrequestid, deleteddocumentmasterids):
            conn = getdbconnection()
            try:
                cursor = conn.cursor()           
                query = '''
                                SELECT dm.recordid, dm.parentid, d.filename as attachmentof, dm.filepath, dm.documentmasterid, da."attributes", 
                                dm.created_at, dm.createdby  
                                FROM "DocumentMaster" dm
                                JOIN "DocumentAttributes" da ON dm.documentmasterid = da.documentmasterid
                                LEFT JOIN "DocumentMaster" dm2 ON dm2.processingparentid = dm.parentid
                                -- replace attachment will create 2 or more rows with the same processing parent id
                                -- we always take the first one since we only need the filename and the user cannot update filename with replace anyways
                                AND dm2.createdby = 'conversionservice' 
                                LEFT JOIN "Documents" d ON dm2.documentmasterid = d.documentmasterid
                                WHERE dm.ministryrequestid = %s::integer
                                AND da.isactive = true
                                AND dm.documentmasterid NOT IN %s
                                ORDER BY da.attributes->>'lastmodified' DESC
                            '''
                parameters = (ministryrequestid, tuple(deleteddocumentmasterids))
                cursor.execute(query, parameters)
                result = cursor.fetchall()
                return result
            except Exception as error:
                logging.error("Error in getdocumentmaster")
                logging.error(error)
                raise
            finally:
                if conn is not None:
                    conn.close()