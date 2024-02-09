from utils import getfoidbconnection
import logging
import json


class documenttypeservice:

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
    