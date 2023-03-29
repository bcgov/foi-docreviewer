
from os import stat
from re import VERBOSE
from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.AnnotationSections import AnnotationSection
from reviewer_api.utils.commons.datetimehandler import datetimehandler
from reviewer_api.models.default_method_result import DefaultMethodResult

import os
import maya
import json

import xml.etree.ElementTree as ET

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

    def saveannotation(self, annotationname, documentid, documentversion, annotationschema, pagenumber, userinfo):
        _annotresponse = Annotation.saveannotation(annotationname, documentid, documentversion, self.__extractannotfromxml(annotationschema['xml']), pagenumber, userinfo)
        if _annotresponse.success == True:
            if "sections" in annotationschema:
                self.saveannotationsection(annotationname, annotationschema, userinfo)
            return DefaultMethodResult(True,'Annotation Section is saved',annotationname)          
        return DefaultMethodResult(False,'Failed to save Annotation Section',annotationname)

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
        firstlist = xmlstring.split('<annots>')
        if len(firstlist) == 2: 
            secondlist = firstlist[1].split('</annots>')
            return secondlist[0]
        return ''
    
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
    
    