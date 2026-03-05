from utils import getfoidbconnection, getdbconnection
import logging
import json


class documenttemplate:
    _DOCREVIEWER_RECORD_MAPPING_QUERY = """
        SELECT d.documentid, dm.recordid
        FROM "Documents" d
        JOIN "DocumentMaster" dm ON d.documentmasterid = dm.documentmasterid
        LEFT JOIN "DocumentDeleted" dd
            ON dm.filepath LIKE '%' || dd.filepath || '%'
            AND dm.ministryrequestid = dd.ministryrequestid
        WHERE d.documentid = ANY(%s)
          AND (d.incompatible IS FALSE OR d.incompatible IS NULL)
          AND (dd.deleted IS FALSE OR dd.deleted IS NULL);
    """

    _FOI_ACTIVE_RECORD_IDS_QUERY = """
        -- Retrieve record groups linked to an FOI request
        SELECT DISTINCT links.record_id
        FROM "FOIRequestRecordGroup" AS group_def
                 JOIN "FOIRequestRecordGroups" AS links
                      ON links.document_set_id = group_def.document_set_id
                 INNER JOIN "FOIRequestRecords" AS records
                            ON links.record_id = records.recordid
        WHERE group_def.request_id = %s
          AND records.isactive = true
          AND links.record_id = ANY (%s);
    """

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
    def getrecordgroupsbyrequestid(cls, request_id, document_ids):
        """
        Retrieve document_ids for record groups linked to an FOI request,
        filtered by a list of document_ids and checking DocReviewer compatibility.
        """
        if not document_ids:
            return []

        recordid_to_docids, record_ids = cls._get_docreviewer_record_mapping(document_ids)
        if not record_ids:
            return []

        valid_record_ids = cls._get_active_foi_record_ids(request_id, record_ids)
        valid_document_ids = cls._map_valid_records_to_document_ids(valid_record_ids, recordid_to_docids)
        return list(set(valid_document_ids))  # Ensure unique document_ids

    @classmethod
    def _get_docreviewer_record_mapping(cls, document_ids):
        doc_conn = getdbconnection()
        try:
            doc_cursor = doc_conn.cursor()
            doc_cursor.execute(cls._DOCREVIEWER_RECORD_MAPPING_QUERY, (document_ids,))
            doc_results = doc_cursor.fetchall()

            recordid_to_docids = {}
            record_ids = []

            for doc_id, rec_id in doc_results:
                if rec_id is not None:
                    if rec_id not in recordid_to_docids:
                        recordid_to_docids[rec_id] = []
                    recordid_to_docids[rec_id].append(doc_id)
                    record_ids.append(rec_id)

            return recordid_to_docids, record_ids

        except Exception as error:
            logging.error("Error retrieving document mappings in getrecordgroupsbyrequestid")
            logging.error(error)
            raise
        finally:
            doc_cursor.close()
            if doc_conn is not None:
                doc_conn.close()

    @classmethod
    def _get_active_foi_record_ids(cls, request_id, record_ids):
        foi_conn = getfoidbconnection()
        try:
            foi_cursor = foi_conn.cursor()
            foi_parameters = (request_id, record_ids)
            foi_cursor.execute(cls._FOI_ACTIVE_RECORD_IDS_QUERY, foi_parameters)
            foi_records = foi_cursor.fetchall()
            return [record[0] for record in foi_records]

        except Exception as error:
            logging.error("Error in getrecordgroupsbyrequestid while querying FOI flow")
            logging.error(error)
            raise
        finally:
            foi_cursor.close()
            if foi_conn is not None:
                foi_conn.close()

    @classmethod
    def _map_valid_records_to_document_ids(cls, valid_record_ids, recordid_to_docids):
        valid_document_ids = []
        for valid_rec_id in valid_record_ids:
            if valid_rec_id in recordid_to_docids:
                valid_document_ids.extend(recordid_to_docids[valid_rec_id])
        return valid_document_ids

    @classmethod
    def getrecordgroupnamesbydocumentsetid(cls, document_set_id):
        """
        Retrieve record group names for a given document_set_id.
        """
        conn = getfoidbconnection()
        try:
            cursor = conn.cursor()

            query = """
                    SELECT name
                    FROM "FOIRequestRecordGroup"
                    WHERE document_set_id = %s; 
                    """

            cursor.execute(query, (document_set_id,))
            records = cursor.fetchall()

            return [record[0] for record in records]

        except Exception as error:
            logging.error("Error in getrecordgroupnamesbydocumentsetid")
            logging.error(error)
            raise

        finally:
            cursor.close()
            if conn is not None:
                conn.close()
