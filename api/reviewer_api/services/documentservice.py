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
            if record["recordid"] is not None:
                record['attachments'] = self.__getattachments(records, record["documentmasterid"])
            record = self.__updatecoversionstatus(conversions, record)
            record = self.__updatededupestatus(dedupes, record)  
            #record = self.__updateproperties(properties, records, record)       
            record = self.__updateredactionstatus(redactions, record)     
        #Duplicate check
        for record in records:
            #record["isduplicate"] = self.__isduplicatenew(records, properties, record)     
            record = self.__updatepropertiesnew(records, properties, record)
        return records
    
    def __updatepropertiesnew(self, records, properties, record): 
        if record["recordid"] is not None:
            record["isduplicate"], record["duplicatemasterid"], record["duplicateof"] = self.__isduplicate(properties, record)
            if len(record["attachments"]) > 0:
                if record["isduplicate"] == True:
                    duplicatemaster_attachments = self.__getduplicatemasterattachments(records, record["duplicatemasterid"])
                    duplicatemaster_attachments.extend(record["attachments"])
                    _att_in_properties = self.__getattachmentproperties(duplicatemaster_attachments, properties)
                else: 
                    _att_in_properties = self.__getattachmentproperties(record["attachments"], properties)
                for attachment in record["attachments"]:
                    print("attachment == ", attachment)                   
                    if attachment["filepath"].endswith(".msg"):
                        attachment["isduplicate"], attachment["duplicatemasterid"], attachment["duplicateof"] = self.__getduplicatemsgattachment(_att_in_properties, attachment)
                    else:
                        attachment["isduplicate"], attachment["duplicatemasterid"], attachment["duplicateof"] = self.__isduplicate(_att_in_properties, attachment)
                    
                
                    # for attachment in record["attachments"]:
                    #     attachment["isduplicate"], attachment["duplicatemasterid"], attachment["duplicateof"] = self.__isduplicate(_att_within_properties, attachment)           
        return record

    def __getduplicatemsgattachment(self, attachmentproperties, attachment):
        _occurances = [d for d in attachmentproperties if d['filename'] == attachment['filename']]
        if len(_occurances) > 1:
            attachment["isduplicate"] = True
            filtered = [x["processingparentid"] for x in attachmentproperties if x["filename"] == attachment["filename"]]
            attachment["duplicatemasterid"] = min(filtered)
            attachment["duplicateof"] = self.__getduplicateof(attachmentproperties, attachment, attachment["duplicatemasterid"] )
            return attachment["isduplicate"], attachment["duplicatemasterid"], attachment["duplicateof"]
        return False, attachment["documentmasterid"], attachment["filename"]
    
    def __getduplicatemasterattachments(self, records, duplicatemasterid):
            for x in records:
                if x["documentmasterid"] == duplicatemasterid:
                    return x["attachments"]

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
        filtered = []
        for entry in records:
            if entry["parentid"] not in [None, ""] and int(entry["parentid"]) == int(documentmasterid):
                result.append(entry)
            else:
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
    
    def __updateproperties(self, properties, records, record):
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
