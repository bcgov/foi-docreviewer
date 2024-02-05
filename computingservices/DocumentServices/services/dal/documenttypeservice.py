from utils import getfoidbconnection
import logging
import json


class documenttypeservice:

    @classmethod 
    def getdocumenttypebyname(cls, document_type_name, extension= "docx"):
        conn = getfoidbconnection()
        try:
            cursor = conn.cursor()
            query = '''
                SELECT *
                FROM public."DocumentTypes" 
                WHERE document_type_name = %s::integer 
                ORDER BY version DESC LIMIT 1;
            '''
            parameters = (document_type_name)
            cursor.execute(query, parameters)
            documenttemplate = cursor.fetchone()[0]
            return documenttemplate
        except Exception as error:
            logging.error("Error in getdocumenttypebyname")
            logging.error(error)
            raise
        finally:
            if conn is not None:
                conn.close()
    