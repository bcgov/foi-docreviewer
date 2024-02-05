from utils import getfoidbconnection
import logging
import json


class documenttemplateservice:

    @classmethod 
    def gettemplatebytype(cls, documenttypeid, extension= "docx"):
        conn = getfoidbconnection()
        try:
            cursor = conn.cursor()
            query = '''
                SELECT *
                FROM public."DocumentTemplates" 
                WHERE document_type_id = %s::integer 
                ORDER BY version DESC LIMIT 1;
            '''
            parameters = (documenttypeid)
            cursor.execute(query, parameters)
            documenttemplate = cursor.fetchone()[0]
            return documenttemplate
        except Exception as error:
            logging.error("Error in gettemplatebytype")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()
    
    @classmethod
    def updatecdogshashcode(cls, documenttypeid, cdogshashcode):
        conn = getfoidbconnection()
        try:        
            cursor = conn.cursor()
            query = '''
                    UPDATE public."DocumentTemplates" SET cdogs_hash_code = %s::str
                    WHERE document_type_id = %s::integer;
                '''
            parameters = (cdogshashcode, documenttypeid,)
            cursor.execute(query, parameters)
            conn.commit()
            cursor.close()
        except(Exception) as error:
            print("Exception while executing func updatecdogshashcode, Error : {0} ".format(error))
            raise
        finally:
            if conn is not None:
                conn.close()