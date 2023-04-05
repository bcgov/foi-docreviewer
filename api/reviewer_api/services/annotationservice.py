
from os import stat
from re import VERBOSE
from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.AnnotationSections import AnnotationSection
from reviewer_api.utils.commons.datetimehandler import datetimehandler
from reviewer_api.models.default_method_result import DefaultMethodResult

import os
import maya
import json

# import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString

class annotationservice:
    """ FOI Annotation management service
    """
    def getannotations(self, documentid, documentversion, pagenumber):
        annotations = Annotation.getannotations(documentid, documentversion)
        annotationlist = []
        for entry in annotations:
            annotationlist.append(entry["annotation"])
        return self.__generateannotationsxml(annotationlist)
    
    def getannotationinfo(self, documentid, documentversion, pagenumber):
        annotations = Annotation.getannotationinfo(documentid, documentversion)
        annotationsections = AnnotationSection.getsectionmapping(documentid, documentversion)
        annotationlist = []
        for entry in annotations:
            section = self.__getsection(annotationsections, entry["annotationname"])
            if self.__issection(annotationsections, entry["annotationname"]) == False:
                if section is not None:     
                    entry['sections'] = {"annotationname": section["sectionannotationname"], "ids": list(map(lambda id: id['id'], json.loads(section["ids"])))}
                annotationlist.append(entry)
        return annotationlist
    
    def __issection(self, annotationsections, annotationname):
        for entry in annotationsections:
            if entry["sectionannotationname"] == annotationname:
                return True
        return False
    
    def __getsection(self, annotationsections, annotationname):
        for entry in annotationsections:
            if entry["redactannotation"] == annotationname:
                return entry
        return None

    def getannotationsections(self, ministryid):
        annotationsections = AnnotationSection.get_by_ministryid(ministryid)
        return annotationsections

    def saveannotation(self, annotationname, documentid, documentversion, annotationschema, userinfo):
        annots = self.__extractannotfromxml(annotationschema['xml'])
        for annot in annots:
            _annotresponse = Annotation.saveannotation(annot["name"], documentid, documentversion, annot["xml"], annot["page"], userinfo)
            if _annotresponse.success == True:
                if "sections" in annotationschema:
                    sectionresponse = self.saveannotationsection(annotationname, annotationschema, userinfo)
                    if not sectionresponse:
                        return DefaultMethodResult(False,'Failed to save Annotation Section',annotationname)
            else:
                return DefaultMethodResult(False,'Failed to save Annotation',annotationname)
        return DefaultMethodResult(True,'Annotation successfully saved',annotationname)

    def saveannotationsection(self, annotationname, annotsectionschema, userinfo):
        ministryid, sectionschema = self.__generateannotsection(annotsectionschema)
        _annotsectionresponse = AnnotationSection.savesection(ministryid, annotationname, sectionschema,userinfo)
        if _annotsectionresponse.success == True:
            return DefaultMethodResult(True,'Annotation is saved',annotationname)     

    def deactivateannotation(self, annotationname, documentid, documentversion, userinfo):
        return Annotation.deactivateannotation(annotationname, documentid, documentversion, userinfo)

    def __getdateformat(self):
        return '%Y %b %d | %I:%M %p'

    def __extractannotfromxml(self, xmlstring):
        xml = parseString(xmlstring)
        annotations = xml.getElementsByTagName("annots")[0].childNodes
        annots = []
        for annot in annotations:
            annots.append({
                "name": annot.getAttribute("name"),
                "page": annot.getAttribute("page"),
                "xml": annot.toxml()
            })
        return annots
    
    def __generateannotationsxml(self, annotations):
        annotationsstring = ''.join(annotations)
        template_path = "reviewer_api/xml_templates/annotations.xml"
        file_dir = os.path.dirname(os.path.realpath('__file__'))
        full_template_path = os.path.join(file_dir, template_path)
        f = open(full_template_path, "r")
        xmltemplatelines = f.readlines()
        xmltemplatestring = ''.join(xmltemplatelines)
        return xmltemplatestring.replace("{{annotations}}", annotationsstring)

    def __generateannotsection(self, annotsectionschema):
        _sectionsschema = annotsectionschema['sections'] if 'sections' in annotsectionschema else annotsectionschema
        return _sectionsschema.pop("foiministryrequestid"), _sectionsschema
    
    