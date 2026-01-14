from utils import getfoidbconnection
import logging
import json


class documenttemplate:

    @classmethod 
    def gettemplatebytype(cls, documenttypeid, extension= "docx"):
        conn = getfoidbconnection()
        try:
            cursor = conn.cursor()
            query = '''
                SELECT cdogs_hash_code
                FROM public."DocumentTemplates" 
                WHERE document_type_id = %s and extension = %s;
            '''
            parameters = (documenttypeid,extension,)
            cursor.execute(query, parameters)
            documenttemplate = cursor.fetchone()[0]
            return documenttemplate
        except Exception as error:
            logging.error("Error in gettemplatebytype")
            logging.error(error)
            raise
        finally:
            cursor.close()
            if conn is not None:
                conn.close()
    
    @classmethod
    def updatecdogshashcode(cls, documenttypeid, cdogshashcode):
        conn = getfoidbconnection()
        try:        
            cursor = conn.cursor()
            query = '''
                    UPDATE public."DocumentTemplates" SET cdogs_hash_code = %s
                    WHERE document_type_id = %s;
                '''
            parameters = (cdogshashcode, documenttypeid,)
            cursor.execute(query, parameters)
            conn.commit()
        except(Exception) as error:
            print("Exception while executing func updatecdogshashcode, Error : {0} ".format(error))
            raise
        finally:
            cursor.close()
            if conn is not None:
                conn.close()

    @classmethod 
    def getdocumenttypebyname(cls, document_type_name):
        conn = getfoidbconnection()
        try:
            cursor = conn.cursor()
            query = '''
                SELECT *
                FROM public."DocumentTypes" 
                WHERE document_type_name = %s;
            '''
            parameters = (document_type_name,)
            cursor.execute(query, parameters)
            documenttemplate = cursor.fetchone()[0]
            return documenttemplate
        except Exception as error:
            logging.error("Error in getdocumenttypebyname")
            logging.error(error)
            raise
        finally:
            cursor.close()
            if conn is not None:
                conn.close()

    @classmethod
    def getrecordgroupsbyrequestid(cls, request_id, record_ids):
        """
        Retrieve record_ids for record groups linked to an FOI request,
        filtered by a list of record_ids.
        """
        conn = getfoidbconnection()
        try:
            cursor = conn.cursor()

            query = """
                    -- Retrieve record groups linked to an FOI request
                    SELECT groups.record_id
                    FROM "FOIRequestRecordGroup" AS req
                             JOIN "FOIRequestRecordGroups" AS groups
                                  ON groups.document_set_id = req.document_set_id
                    WHERE req.request_id = %s
                      AND groups.record_id = ANY (%s); 
                    """

            parameters = (request_id, record_ids)
            cursor.execute(query, parameters)
            
            records = cursor.fetchall()
            return [record[0] for record in records]

        except Exception as error:
            logging.error("Error in getrecordgroupsbyrequestid")
            logging.error(error)
            raise

        finally:
            cursor.close()
            if conn is not None:
                conn.close()
