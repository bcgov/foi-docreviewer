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

    def getdedupestatus(self, requestid):
        """ Returns the active records
        """
        documents = Document.getdocumentsdedupestatus(requestid)
        for document in documents:
            document['created_at'] = pstformat(document['created_at'])
            document['updated_at'] = pstformat(document['updated_at'])

        return documents
    def getdocuments_updated(self, requestid):
        deleted = DocumentMaster.getdeleted(requestid)
        documenthashproperties = DocumentMaster.getdocumentshashproperty(requestid, deleted)
        records = DocumentMaster.getdocumentmaster(requestid)
        divisions = ProgramAreaDivision.getallprogramareadivisons()
        
        records = [entry for entry in records if entry['documentmasterid'] not in deleted]
        documents = []
        for record in records:
            record["ministryrequestid"] =  requestid
            record["isattachment"] = True if record["parentid"] is not None else False
            record["isduplicate"] = False
            record = self.__updatedocumenthashproperties(documenthashproperties, record)
            # document = self.__preparedocument(record, requestid, divisions)
            # if document:
            #     documents.append(document)

        records = self.__updatedocumenthashpropertiesforattachments(documenthashproperties, records)
        return self.__preparedocuments(records, requestid, divisions)

    def __preparedocuments(self, records, requestid, divisions):
        documents = []
        for record in records:
            if record["isduplicate"] or record["incompatible"]:
                return
            
            document = {}
            document["documentid"] = record["documentid"]
            document["version"] = record["version"]
            document["filename"] = record["filename"]
            document["filepath"] = record["filepath"]
            document["attributes"] = record["attributes"]
            document["foiministryrequestid"] = requestid
            document["createdby"] = record["createdby"]
            document["created_at"] = record["created_at"]
            document["updatedby"] = record["updatedby"]
            document["updated_at"] = record["updated_at"]
            document["statusid"] = record["statusid"]
            document["status"] = record["status"]
            document["pagecount"] = record["pagecount"]
            doc_divisions = []
            for division in record["attributes"]["divisions"]:
                    doc_division = [div for div in divisions if div['divisionid']==division['divisionid']][0]
                    doc_divisions.append(doc_division)

            document['divisions'] = doc_divisions
            documents.append(document)
        return documents
    
    def __updatedocumenthashproperties(self, properties, record):
        for property in properties:
            if record["documentmasterid"] == property["processingparentid"] or (property["processingparentid"] is None and record["documentmasterid"] == property["documentmasterid"]):
                record["pagecount"] = property["pagecount"]
                record["filename"] = property["filename"]
                record["isduplicate"], record["duplicatemasterid"], record["duplicateof"] =  self.__isduplicate(properties, record)
                record["incompatible"] = property["incompatible"]
                record["documentid"] = property["documentid"]
                record["version"] = property["version"]
                record["filepath"] = property["filepath"]
                record["createdby"] = property["createdby"]
                record["created_at"] = pstformat(property["created_at"])
                record["updatedby"] = property["updatedby"]
                record["updated_at"] = pstformat(property["updated_at"])
                record["statusid"] = property["statusid"]
                record["status"] = property["status"]
        return record
    
    def __updatedocumenthashpropertiesforattachments(self, properties, records):
        parentids = self.__getduplicateparentids(records)
        for record in records:
            if record["parentid"] in parentids:
                record["isduplicate"], record["duplicatemasterid"], record["duplicateof"] =  self.__isduplicate(properties, record, True)
        return records

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
            record["isduplicate"] = record["isredactionready"] = False
            record = self.__updatecoversionstatus(conversions, record)
            record = self.__updatededupestatus(dedupes, record)  
            record = self.__updateproperties(properties, records, record)       
            record = self.__updateredactionstatus(redactions, record) 
        print("records BEFORE attachments =>>>> ", records)
        records = self.__updatepropertiesforattachments(properties, records)
        print("records AFTER attachments =>>>> ", records)
        return records
    
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
        """ Sets the iduplicate value for Parent records
        """
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
                # print("__updateproperties filename = ",record["filename"])
                _uploaded = self.__getuploadedrecord(records, record["parentid"]) 
                _occurances = [d for d in properties if d['filename']==record['filename']]
                if len(_occurances) > 1:
                    # print("_occurances > 1 = ", _occurances)
                    # print("_uploaded ==== >>> ", _uploaded)
                    record["isduplicate"], record["duplicatemasterid"],record["duplicateof"]  =  self.__isduplicate(properties, _uploaded, True)
                    # print("duplicatemasterid === ", record["duplicatemasterid"])
                    childmasterids = []
                    for _record in records:
                        if _record["parentid"] == record["duplicatemasterid"]:
                            childmasterids.append(_record["documentmasterid"])
                    # print("childmasterids === ", childmasterids)
                    if record["isduplicate"] == True:
                        filtered = [x["processingparentid"] for x in properties if x["filename"] == record["filename"] and x["processingparentid"] in childmasterids]
                        record["duplicatemasterid"] = min(filtered)
                        record["duplicateof"] = self.__getduplicateof(properties, record, record["duplicatemasterid"] )
            """End

            Duplicate block check end
            """
        return record

    def __updatepropertiesforattachments(self, properties, records):

        """
        get all the parentids with isduplicate=True
        """

        duplicateparentids = self.__getduplicateparentids(records)

        print("duplicateparentids = ", duplicateparentids)

        """
        set isduplicate, duplicatemasterid and duplicateof properties for attachments
        """
        for record in records:
            if record["isduplicate"] == False and record["parentid"] is not None and record["parentid"] in duplicateparentids:
                # if record["filepath"].endswith(".msg"):
                    print("__updatepropertiesforattachments filename = ",record["filename"])
                    _parentrecord = self.__getparentrecord(records, record["parentid"]) 
                    _occurances = [d for d in properties if d['filename']==record['filename']]
                    if len(_occurances) > 1:
                        # record["isduplicate"], record["duplicatemasterid"],record["duplicateof"]  =  self.__isduplicate(properties, _parentrecord, True)
                        # print("duplicatemasterid === ", record["duplicatemasterid"])
                        childmasterids = []
                        for _record in records:
                            if _parentrecord["isduplicate"] and _record["parentid"] == _parentrecord["duplicatemasterid"]:
                                childmasterids.append(_record["documentmasterid"])
                        print("childmasterids === ", childmasterids)
                        if len(childmasterids) > 0:
                            filtered = [x["processingparentid"] if x["processingparentid"] is not None else x["documentmasterid"] for x in properties if x["filename"] == record["filename"] and (x["processingparentid"] in childmasterids or x["documentmasterid"] in childmasterids)]

                            # filtered = [x["processingparentid"] if x["processingparentid"] is not None else x["documentmasterid"] for x in properties if x["filename"] == record["filename"]]
                            print("filtered == ", filtered)
                            if len(filtered) > 0:
                                record["isduplicate"] = True
                                record["duplicatemasterid"] = min(filtered)
                                record["duplicateof"] = self.__getduplicateof(properties, record, record["duplicatemasterid"] )
                # else:
                #     record["isduplicate"], record["duplicatemasterid"], record["duplicateof"] =  self.__isduplicate(properties, record, True)
            

        return records
    def __getparentrecord(self, records, masterid):
        for record in records:
            if record["documentmasterid"] == masterid:
                    return record

    def __updateredactionstatus(self,redactions, record):
        for entry in redactions:
            if record["documentmasterid"] == entry["processingparentid"] or (entry["processingparentid"] is None and record["documentmasterid"]  == entry["documentmasterid"]):
                record["isredactionready"] = entry["isredactionready"]
        return record
        
    def __isduplicate(self, properties, record, checkattachments=False):
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
            if originalid != record["documentmasterid"] and (record["parentid"] is None or checkattachments):
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
    def __getduplicateparentids(self, records):
        parentids = []
        for record in records:
            if record["isduplicate"]:
                parentids.append(record["documentmasterid"])
        return parentids
    
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
