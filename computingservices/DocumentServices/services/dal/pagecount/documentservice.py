from utils import getdbconnection
import logging
from utils.basicutils import to_json


class documentservice:

    @classmethod
    def pagecalculatorjobstart(cls, message):
        conn = getdbconnection()
        try:
                    
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO public."PageCalculatorJob"
                (pagecalculatorjobid, version, ministryrequestid, inputmessage, status, createdby)
                VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s) on conflict (pagecalculatorjobid, version) do nothing returning pagecalculatorjobid;''',
                (message.jobid, 2, message.ministryrequestid, to_json(message), 'started', message.createdby))
            conn.commit()
            cursor.close()
        except(Exception) as error:
            print("Exception while executing func recordjobstart (p6), Error : {0} ".format(error))
            raise
        finally:
            if conn is not None:
                conn.close()

    @classmethod
    def pagecalculatorjobend(cls, jsonmessage, error, pagecount="", message=""):
        conn = getdbconnection()
        try: 
            
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO public."PageCalculatorJob"
                (pagecalculatorjobid, version, ministryrequestid, inputmessage, pagecount, status, createdby, message)
                VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s) on conflict (pagecalculatorjobid, version) do nothing returning pagecalculatorjobid;''',
                (jsonmessage.jobid, 3, jsonmessage.ministryrequestid, to_json(jsonmessage), to_json(pagecount), 'error' if error else 'completed', jsonmessage.createdby, message if error else ""))
                conn.commit()
                cursor.close()
            
        except(Exception) as error:
            print("Exception while executing func recordjobend (p7), Error : {0} ".format(error))
            raise
        finally:
            if conn is not None:
                conn.close()
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
      
        if len(deleteddocumentmasterids) == 0:
            deleteddocumentmasterids = [0]
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
                    AND da.attributes->>'incompatible' = 'false'
                    AND dm.documentmasterid NOT IN %s
                    ORDER BY da.attributes->>'lastmodified' DESC
                '''
            parameters = (ministryrequestid, tuple(deleteddocumentmasterids))
            cursor.execute(query, parameters)
            result = cursor.fetchall()
            documentmaster = []
            for row in result:
                document = {}
                document["recordid"] = row[0]
                document["parentid"] = row[1]
                document["attachmentof"] = row[2]
                document["filepath"] = row[3]
                document["documentmasterid"] = row[4]
                document["attributes"] = row[5]
                document["created_at"] = row[6]
                document["createdby"] = row[7]
                documentmaster.append(document)
            return documentmaster
        except Exception as error:
            logging.error("Error in getdocumentmaster")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()

    @classmethod
    def getdocumentproperties(cls, ministryrequestid, deleteddocumentmasterids):
        if len(deleteddocumentmasterids) == 0:
            deleteddocumentmasterids = [0]
        conn = getdbconnection()
        try:
            cursor = conn.cursor()           
            query = '''
                    SELECT dm.documentmasterid,  dm.processingparentid, d.documentid, d.version,
                    dhc.rank1hash, d.filename, d.pagecount, dm.parentid 
                    FROM "DocumentMaster" dm 
                    INNER JOIN "Documents" d 
                    ON dm.ministryrequestid  = d.foiministryrequestid
                    AND dm.documentmasterid = d.documentmasterid
                    AND dm.ministryrequestid = %s::integer
                    AND dm.documentmasterid NOT IN %s
                    INNER JOIN "DocumentHashCodes" dhc ON d.documentid = dhc.documentid						
                    ORDER BY dm.documentmasterid
                '''
            parameters = (ministryrequestid, tuple(deleteddocumentmasterids))
            cursor.execute(query, parameters)
            result = cursor.fetchall()
            properties = []
            for row in result:
                property = {}
                property["documentmasterid"] = row[0]
                property["processingparentid"] = row[1]
                property["documentid"] = row[2]
                property["version"] = row[3]
                property["rank1hash"] = row[4]
                property["filename"] = row[5]
                property["pagecount"] = row[6]
                property["parentid"] = row[7]
                properties.append(property)
            return properties
        except Exception as error:
            logging.error("Error in getdocumentproperties")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()

    @classmethod
    def getdedupestatus(cls, ministryrequestid):
        conn = getdbconnection()
        try:
            cursor = conn.cursor()           
            query = '''
                    SELECT DISTINCT ON (deduplicationjobid) deduplicationjobid, version, documentmasterid, filename  
                    FROM "DeduplicationJob" fcj  WHERE ministryrequestid = %s::integer
                    ORDER BY deduplicationjobid, "version" DESC
                '''
            parameters = (ministryrequestid,)
            cursor.execute(query, parameters)
            result = cursor.fetchall()
            dedupe = []
            for row in result:
                document = {}
                document["deduplicationjobid"] = row[0]
                document["version"] = row[1]
                document["documentmasterid"] = row[2]
                document["filename"] = row[3]
                dedupe.append(document)
            return dedupe
        except Exception as error:
            logging.error("Error in getdedupestatus")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()