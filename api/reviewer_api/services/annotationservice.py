from os import stat
from re import VERBOSE
from reviewer_api.models.Documents import Document
from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.AnnotationSections import AnnotationSection
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.DocumentPageflags import DocumentPageflag

from reviewer_api.schemas.annotationrequest import SectionAnnotationSchema

from reviewer_api.models.default_method_result import DefaultMethodResult

from reviewer_api.services.redactionlayerservice import redactionlayerservice


import os
import maya
import json
import pytz
from xml.dom.minidom import parseString


class annotationservice:
    """FOI Annotation management service"""
    
    def getrequestannotations(self, ministryrequestid, mappedlayerids):
        annotations = Annotation.getrequestannotations(
            ministryrequestid, mappedlayerids
        )
        annotationobj = {}
        for annot in annotations:
            if annot["documentid"] not in annotationobj:
                annotationobj[annot["documentid"]] = []
            annotationobj[annot["documentid"]].append(annot["annotation"])
        for documentid in annotationobj:
            annotationobj[documentid] = self.__generateannotationsxml(
                annotationobj[documentid]
            )
        return annotationobj

    def getrequestannotationspagination(
        self, ministryrequestid, mappedlayerids, page, size
    ):
        result = Annotation.get_request_annotations_pagination(
            ministryrequestid, mappedlayerids, page, size
        )
        meta = {
            "page": result.page,
            "pages": result.pages,
            "total": result.total,
            "prev_num": result.prev_num,
            "next_num": result.next_num,
            "has_next": result.has_next,
            "has_prev": result.has_prev,
        }
        return {"data": self.__formatannotations(result.items), "meta": meta}
    
    def getdocumentannotations(self, ministryrequestid, mappedlayerids, documentid):
        result = Annotation.get_document_annotations(ministryrequestid, mappedlayerids, documentid)
        return {documentid: result}

    def __formatannotations(self, annotations):
        annotationobj = {}
        for annot in annotations:
            if annot.documentid not in annotationobj:
                annotationobj[annot.documentid] = []
            annotationobj[annot.documentid].append(annot.annotation)
        for documentid in annotationobj:
            annotationobj[documentid] = self.__generateannotationsxml(
                annotationobj[documentid]
            )
        return annotationobj

    


    def getrequestannotationinfo(self, ministryrequestid, redactionlayer):
        redactionlayerid = redactionlayerservice().getredactionlayerid(redactionlayer)
        annotationsections = AnnotationSection.getsectionmappingbyrequestid(
            ministryrequestid, redactionlayerid
        )
        for entry in annotationsections:
            entry["sections"] = {
                "annotationname": entry.pop("sectionannotation"),
                "ids": list(map(lambda id: id["id"], json.loads(entry.pop("ids")))),
            }
        return annotationsections

    def getredactedsectionsbyrequest(self, ministryrequestid):
        sections = {}
        layers = redactionlayerservice().getall()
        for layer in layers:
            if layer["name"] in ["Redline", "OIPC"]:
                redactedsections = AnnotationSection.getredactedsectionsbyrequest(ministryrequestid, layer["redactionlayerid"])
                if redactedsections not in (None, ""):
                    sections[layer["name"]] = redactedsections
        return sections

    def getannotationsections(self, ministryid, redactionlayerid):
        annotationsections = AnnotationSection.get_by_ministryid(ministryid, redactionlayerid)
        return annotationsections

    def copyannotation(self, ministryrequestid, sourcelayers, targetlayer):
        documentids = Document.getdocumentidsbyrequest(ministryrequestid)
        #Additional Check to ensure double copy do not happen
        iscopied = Annotation.isannotationscopied(documentids, targetlayer)
        if iscopied == False:
            annotresponse = Annotation.copyannotations(documentids, sourcelayers, targetlayer)
            if annotresponse.success == True:
                AnnotationSection.copyannotationsections(ministryrequestid, sourcelayers, targetlayer)
                DocumentPageflag.copydocumentpageflags(ministryrequestid, sourcelayers, targetlayer)  
            return DefaultMethodResult(True, "Copied Annotations", ministryrequestid)
        return DefaultMethodResult(False, "Annotations already exist", targetlayer)


    def saveannotation(self, annotationschema, userinfo):
        annots = self.__extractpolygonannotfromxml(annotationschema) if annotationschema["ispolygon"] else self.__extractannotfromxml(annotationschema["xml"])
        _redactionlayerid = self.__getredactionlayerid(annotationschema)
        if len(annots) < 1:
            return DefaultMethodResult(True, "No valid Annotations found", -1)
        resp = Annotation.saveannotations(annots, _redactionlayerid, userinfo)
        if resp.success == True:
            if "sections" in annotationschema:
                sectionresponse = AnnotationSection.savesections(
                    annots,
                    _redactionlayerid,
                    annotationschema["sections"]["foiministryrequestid"],
                    userinfo,
                )
                if not sectionresponse:
                    return DefaultMethodResult(
                        False, "Failed to save Annotation Section", resp.identifier
                    )
        else:
            return DefaultMethodResult(
                False, "Failed to save Annotation", resp.identifier
            )
        # Collect all existing IDS
        delete_annots = [
            item["existingid"] for item in annots if item["existingid"] is not None
        ]
        if len(delete_annots) > 0:
            self.__deleteannotations(delete_annots, _redactionlayerid, userinfo)
        return DefaultMethodResult(
            True, "Annotation successfully saved", resp.identifier
        )

    def deactivateannotation(self, annotationnames, redactionlayerid, userinfo):
        return self.__deleteannotations(annotationnames, redactionlayerid, userinfo)
    
    async def deactivatedocumentannotations(self, documentids, userinfo):
        return Annotation.deletedocumentannotations(documentids, userinfo)

    def __deleteannotations(self, annotationnames, redactionlayerid, userinfo):
        if annotationnames not in (None, []) and len(annotationnames) > 0:
            resp = Annotation.bulkdeleteannotations(
                annotationnames, redactionlayerid, userinfo
            )
            if resp.success == True:
                AnnotationSection.bulkdeletesections(annotationnames, redactionlayerid, userinfo)
            return resp
        return DefaultMethodResult(True, "No Annotations marked for delete", -1)

    def __getdateformat(self):
        return "%Y %b %d | %I:%M %p"

    def __extractannotfromxml(self, xmlstring):
        xml = parseString(xmlstring)
        annotations = xml.getElementsByTagName("annots")[0].childNodes
        annots = []
        for annot in annotations:
            if self.__isvalid(annot) == True:
                formatted_utc = self.__converttoutctime(annot)
                customdata = annot.getElementsByTagName("trn-custom-data")[
                    0
                ].getAttribute("bytes")
                customdatadict = json.loads(customdata)
                if formatted_utc is not None:
                    annot.setAttribute("creationdate", formatted_utc)
                    annot.setAttribute("date", formatted_utc)
                annots.append(
                    {
                        "name": annot.getAttribute("name"),
                        "page": customdatadict["originalPageNo"],
                        "xml": annot.toxml(),
                        "sectionsschema": SectionAnnotationSchema().loads(customdata),
                        "docid": customdatadict["docid"],
                        "docversion": customdatadict["docversion"]
                        if "docversion" in customdatadict
                        else 1,
                        "existingid": customdatadict["existingId"]
                        if "existingId" in customdatadict
                        else None,
                    }
                )
        return annots
    
    def __extractpolygonannotfromxml(self, annotationschema):        
        xml = parseString(annotationschema['xml'])
        annotations = xml.getElementsByTagName("annots")[0]
        annots = []
        # get stored values from first annot in array
        annot = annotations.childNodes[0]
        formatted_utc = self.__converttoutctime(annot)
        customdata = annot.getElementsByTagName("trn-custom-data")[
            0
        ].getAttribute("bytes")
        customdatadict = json.loads(customdata)
        if formatted_utc is not None:
            annot.setAttribute("creationdate", formatted_utc)
            annot.setAttribute("date", formatted_utc)
        annots.append(
            {
                "name": annotationschema["name"],
                "page": customdatadict["originalPageNo"],
                "xml": annotations.toxml().replace('\n', '').replace('\t', '').replace('<annots>', '').replace('</annots>', ''),
                "sectionsschema": SectionAnnotationSchema().loads(customdata),
                "docid": customdatadict["docid"],
                "docversion": customdatadict["docversion"]
                if "docversion" in customdatadict
                else 1,
                "existingid": customdatadict["existingId"]
                if "existingId" in customdatadict
                else None,
            }
        )
        return annots


    def __generateannotationsxml(self, annotations):
        annotationsstring = "".join(annotations)
        template_path = "reviewer_api/xml_templates/annotations.xml"
        file_dir = os.path.dirname(os.path.realpath("__file__"))
        full_template_path = os.path.join(file_dir, template_path)
        f = open(full_template_path, "r")
        xmltemplatelines = f.readlines()
        xmltemplatestring = "".join(xmltemplatelines)
        return xmltemplatestring.replace("{{annotations}}", annotationsstring)

    def __getredactionlayerid(self, annotationschema):
        if "redactionlayerid" in annotationschema and annotationschema[
            "redactionlayerid"
        ] not in (None, ""):
            return int(annotationschema["redactionlayerid"])
        else:
            return redactionlayerservice().getdefaultredactionlayerid()

    def __isvalid(self, annot):
        if annot is not None and annot.tagName == "redact":
            if annot.getAttribute("inreplyto") not in (None, ""):
                return True
            return False
        return True

    def __converttoutctime(self, annot):
        original_timestamp = annot.getAttribute("creationdate")
        # Extract date and time components from the timestamp
        timestamp_str = original_timestamp[2:]  # Remove the leading "D:"
        timestamp_str = timestamp_str.replace("'", ":")  # Replace single quotes
        if timestamp_str.endswith(":"):
            timestamp_str = timestamp_str[:-1]
        timestamp_utc = maya.parse(timestamp_str).datetime().astimezone(pytz.UTC)
        # Format the UTC time in the same format as the original timestamp
        formatted_utc = "D:" + timestamp_utc.strftime("%Y%m%d%H%M%S")
        return formatted_utc
