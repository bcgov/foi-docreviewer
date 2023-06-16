from reviewer_api.models.Documents import Document
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.FileConversionJob import FileConversionJob
from reviewer_api.models.DeduplicationJob import DeduplicationJob
from datetime import datetime as datetime2
from os import path
from reviewer_api.models.DocumentDeleted import DocumentDeleted
import json
from reviewer_api.utils.util import pstformat
from reviewer_api.models.ProgramAreaDivisions import ProgramAreaDivision
from reviewer_api.models.DocumentAttributes import DocumentAttributes

class documentservice:

    
    def getdedupestatus(self,requestid):
        deleted = DocumentMaster.getdeleted(requestid)
        records = DocumentMaster.getdocumentmaster(requestid)
        conversions = FileConversionJob.getconversionstatus(requestid)
        dedupes = DeduplicationJob.getdedupestatus(requestid)
        properties = DocumentMaster.getdocumentproperty(requestid, deleted)
        redactions = DocumentMaster.getredactionready(requestid)
        records = [entry for entry in records if entry['documentmasterid'] not in deleted]
        for record in records:
            record["duplicatemasterid"] = record["documentmasterid"]
            record["ministryrequestid"] =  requestid
            record["isattachment"] = True if record["parentid"] is not None else False
            record['created_at'] = pstformat(record['created_at'])
            record["conversionstatus"] = record["deduplicationstatus"] = None
            record["isredactionready"] = False
            record = self.__updatecoversionstatus(conversions, record)
            record = self.__updatededupestatus(dedupes, record)
            record = self.__updateredactionstatus(redactions, record)
            if record["recordid"] is not None:
                record['attachments'] = self.__getattachments(records, record["documentmasterid"])

        #Duplicate check
        finalresults = []
        for record in records:            
            if record["recordid"] is not None:
                finalresult = self.__updateproperties(records, properties, record)
                finalresults.append(finalresult)
        print("finalresults ======= >>>>>>>> ", finalresults)    
        return finalresults
    
    def __updateproperties(self, records, properties, record):
        if record["recordid"] is not None:
            _att_in_properties = []
            parentrecords = self.__getparentrecords(records)
            parentproperties = self.__getrecordsproperties(parentrecords, properties)
            record["pagecount"], record["filename"] = self.__getpagecountandfilename(record, parentproperties)
            record["isduplicate"], record["duplicatemasterid"], record["duplicateof"] = self.__isduplicate(parentproperties, record)
            if len(record["attachments"]) > 0:
                if record["isduplicate"] == True:
                    duplicatemaster_attachments = self.__getduplicatemasterattachments(records, record["duplicatemasterid"])                    
                    _att_in_properties = self.__getattachmentproperties(duplicatemaster_attachments + record["attachments"], properties)
                elif len(record["attachments"]) > 1: 
                    _att_in_properties = self.__getattachmentproperties(record["attachments"], properties)
                for attachment in record["attachments"]:
                    if len(_att_in_properties) > 0:
                        if attachment["filepath"].endswith(".msg"):
                            attachment["isduplicate"], attachment["duplicatemasterid"], attachment["duplicateof"] = self.__getduplicatemsgattachment(records, _att_in_properties, attachment)
                        else:
                            attachment["isduplicate"], attachment["duplicatemasterid"], attachment["duplicateof"] = self.__isduplicate(_att_in_properties, attachment)
                    
                        attachment["pagecount"], attachment["filename"] = self.__getpagecountandfilename(attachment, _att_in_properties)
        return record
    def __getparentrecords(self, records):
        filtered = []
        for record in records:
            if record["recordid"] is not None:
                filtered.append(record)
        return filtered
    
    def __getpagecountandfilename(self, record, properties):
        pagecount = 0
        filename = record["filename"] if "filename" in record else None
        for property in properties:
            if record["documentmasterid"] == property["processingparentid"] or (property["processingparentid"] is None and record["documentmasterid"] == property["documentmasterid"]):
                pagecount = property["pagecount"]
                filename = property["filename"]
        return pagecount, filename

    def __getduplicatemsgattachment(self, records, attachmentproperties, attachment):
        _occurances = []
        for entry in attachmentproperties:
            if entry["filename"] == attachment['filename']:
                _lhsattribute = self.__getrecordproperty(records, entry["processingparentid"], "attributes")
                _rhsattribute = self.__getrecordproperty(records, attachment["documentmasterid"], "attributes")
                if _lhsattribute["filesize"] ==  _rhsattribute["filesize"] and _lhsattribute["lastmodified"] ==  _rhsattribute["lastmodified"]:
                    _occurances.append(entry)  
        if len(_occurances) > 1:
            filtered = [x["processingparentid"] for x in _occurances] 
            _firstupload = min(filtered)
            if _firstupload != attachment["documentmasterid"]:
                attachment["isduplicate"] = True            
                attachment["duplicatemasterid"] = _firstupload
                attachment["duplicateof"] = self.__getduplicateof(attachmentproperties, attachment, attachment["duplicatemasterid"] )
                return attachment["isduplicate"], attachment["duplicatemasterid"], attachment["duplicateof"]
        return False, attachment["documentmasterid"], attachment["filename"]
    
    def __getduplicatemasterattachments(self, records, duplicatemasterid):
            return self.__getrecordproperty(records, duplicatemasterid, "attachments")

    def __getrecordproperty(self, records, documentmasterid, property):
        for x in records:
            if x["documentmasterid"] == documentmasterid:
                return x[property] 
        return None  

    def __getrecordsproperties(self, records, properties):
        filtered = [] 
        for record in records:
            for property in properties:
                if property["processingparentid"] == record["documentmasterid"] or (property["processingparentid"] is None and record["documentmasterid"] == property["documentmasterid"]):
                    filtered.append(property)
        return filtered
    def __getattachmentproperties(self, attachments, properties):
        filtered = [] 
        for attachment in attachments:
            for property in properties:
                if property["processingparentid"] == attachment["documentmasterid"] or (property["processingparentid"] is None and attachment["documentmasterid"] == property["documentmasterid"]):
                    filtered.append(property)
        return filtered

    def __getattachments(self, records, documentmasterid):
        result = []
        filtered, result = self.__attachments2(records, result, documentmasterid)
        for subentry in result:
            filtered, result = self.__attachments2(filtered, result, subentry["documentmasterid"])
        return result
    
    def __attachments2(self, records, result, documentmasterid):
        # print("documentmasterid === ", documentmasterid)
        filtered = []
        for entry in records:            
            if entry["recordid"] is None:
                # print("entry === ", entry)
                if entry["parentid"] not in [None, ""] and int(entry["parentid"]) == int(documentmasterid):
                    # print("<<<< inside if >>>>")
                    result.append(entry)
                else:
                    # print("<<<< inside else >>>>")
                    filtered.append(entry)
        return filtered, result  

    def __updatecoversionstatus(self, conversions, record):
        for conversion in conversions:
            if record["documentmasterid"] == conversion["documentmasterid"]:
                record["conversionstatus"] = conversion["status"]
                record["outputdocumentmasterid"] = conversion["outputdocumentmasterid"]
                record["filename"] = conversion["filename"]
                record["trigger"] = conversion["trigger"]
        return record    
    
    def __updatededupestatus(self, dedupes, record):
        for dedupe in dedupes:
            if record["documentmasterid"] == dedupe["documentmasterid"]:
                record["deduplicationstatus"] = dedupe["status"] 
                record["filename"] = dedupe["filename"]
                record["trigger"] = dedupe["trigger"]
        return record 
    
    def __updateproperties_old(self, properties, records, record):
        for property in properties:
            if record["documentmasterid"] == property["processingparentid"] or (property["processingparentid"] is None and record["documentmasterid"] == property["documentmasterid"]):
                record["pagecount"] = property["pagecount"]
                record["isduplicate"], record["duplicatemasterid"], record["duplicateof"] =  self.__isduplicate(properties, record)
                record["filename"] = property["filename"]
        """Begin        
        Below block is a temporary workaround to verify duplicate in msg.
        This verifies the duplicate with the parent hashcode and filename
        """
        if record["isduplicate"] == False and record["parentid"] is not None and record["filepath"].endswith(".msg"):
            _uploaded = self.__getuploadedrecord(records, record["parentid"]) 
            _occurances = [d for d in properties if d['filename']==record['filename']]
            if len(_occurances) > 1:
                record["isduplicate"], record["duplicatemasterid"],record["duplicateof"]  =  self.__isduplicate(properties, _uploaded)
                if record["isduplicate"] == True:
                    filtered = [x["processingparentid"] for x in properties if x["filename"] == record["filename"]]
                    record["duplicatemasterid"] = min(filtered)
                    record["duplicateof"] = self.__getduplicateof(properties, record, record["duplicatemasterid"] )
        """End

        Duplicate block check end
        """
        return record   
    
    def __updateredactionstatus(self,redactions, record):
        for entry in redactions:
            if record["documentmasterid"] == entry["processingparentid"] or (entry["processingparentid"] is None and record["documentmasterid"]  == entry["documentmasterid"]):
                record["isredactionready"] = entry["isredactionready"]
        return record
        
    def __isduplicate(self, properties, record):        
        matchedhash = None
        isduplicate = False
        duplicatemasterid = record["documentmasterid"]
        duplicateof = record["filename"] if "filename" in record else None
        for property in properties:
            if property["processingparentid"] == record["documentmasterid"] or (property["processingparentid"] is None and record["documentmasterid"] == property["documentmasterid"]):
                matchedhash = property["rank1hash"] 
        filtered = []
        for x in properties:
            if x["rank1hash"] == matchedhash:
                value = x["processingparentid"] if x["processingparentid"] is not None else x["documentmasterid"]
                filtered.append(value)
        if len(filtered) > 1 and filtered not in (None, []):            
            originalid = min(filtered)
            if  originalid != record["documentmasterid"]:
                isduplicate = True
                duplicatemasterid = originalid
                duplicateof = self.__getduplicateof(properties, record, originalid)
        return isduplicate, duplicatemasterid, duplicateof

    def __getduplicateof(self, properties, record, duplicatemasterid):
        duplicateof = record["filename"] if "filename" in record else None
        if duplicateof is None:
            return None
        for z in properties:
            if (duplicatemasterid == z["processingparentid"]) or (z["processingparentid"] is None and duplicatemasterid == z["documentmasterid"]):
                duplicateof = z["filename"] 
        return duplicateof
        
    def __getuploadedrecord(self, records, masterid):
        for record in records:
            if record["documentmasterid"] == masterid:
                if record["parentid"] is None and record["recordid"] is not None:
                    return record
                else:
                    return self.__getuploadedrecord(records, record["parentid"])
        return None

    def deletedocument(self, payload, userid):
        """ Inserts document into list of deleted documents
        """
        return DocumentDeleted.create([
            DocumentDeleted(
                filepath=path.splitext(filepath)[0],
                ministryrequestid = payload["ministryrequestid"],
                deleted=True,
                createdby=userid,
                created_at=datetime2.now()

            ) for filepath in payload['filepaths']
        ])

    def updatedocumentattributes(self, payload, userid):
        """ update document attributes
        """

        docattributeslist = DocumentAttributes.getdocumentattributesbyid(payload['documentmasterids'])
        oldRows = []
        newRows = []
        for docattributes in docattributeslist:
            oldRows.append(
                {
                    'attributeid': docattributes['attributeid'],
                    'version': docattributes['version'],
                    'documentmasterid': docattributes['documentmasterid'],
                    'attributes': docattributes['attributes'],
                    'createdby': docattributes['createdby'],
                    'created_at': docattributes['created_at'],
                    'updatedby': userid,
                    'updated_at': datetime2.now(),
                    'isactive': False
                }
            )
            newdocattributes = json.loads(json.dumps(docattributes['attributes']))
            newdocattributes['divisions'] = payload['divisions']
            newRows.append(
                DocumentAttributes(
                    version = docattributes['version']+1,
                    documentmasterid = docattributes['documentmasterid'],
                    attributes = newdocattributes,
                    createdby = docattributes['createdby'],
                    created_at = docattributes['created_at'],
                    isactive = True
                )
            )

        return DocumentAttributes.create(newRows, oldRows)

    def getdocuments(self, requestid):
        documents = Document.getdocuments(requestid)
        divisions = ProgramAreaDivision.getallprogramareadivisons()

        formated_documents = []
        for document in documents:
            doc_divisions = []
            for division in document['divisions']:
                doc_division = [div for div in divisions if div['divisionid']==division['divisionid']][0]
                doc_divisions.append(doc_division)

            document['divisions'] = doc_divisions
            formated_documents.append(document)

        return documents
    
    def getdocument(self, documentid):
        return Document.getdocument(documentid)    
    
    
    def savedocument(self, documentid, documentversion, newfilepath, userid):
        return

    def deleterequestdocument(self, documentid, documentversion):
        return
