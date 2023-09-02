
from os import stat
from re import VERBOSE
from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.AnnotationSections import AnnotationSection
from reviewer_api.schemas.annotationrequest import SectionAnnotationSchema

from reviewer_api.models.default_method_result import DefaultMethodResult

from reviewer_api.services.redactionlayerservice import redactionlayerservice


import os
import maya
import json

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
    
    def getrequestannotations(self, ministryrequestid, mappedlayerids):
        annotations = Annotation.getrequestannotations(ministryrequestid, mappedlayerids)
        annotationobj = {}
        for annot in annotations:
            if annot['documentid'] not in annotationobj:
                annotationobj[annot['documentid']] = []
            annotationobj[annot['documentid']].append(annot["annotation"])
        for documentid in annotationobj:
            annotationobj[documentid] = self.__generateannotationsxml(annotationobj[documentid])
        return annotationobj
    
    def getrequestdivisionannotations(self, ministryrequestid, divisionid):
        annotations = Annotation.getrequestdivisionannotations(ministryrequestid, divisionid)
        annotationobj = {}
        for annot in annotations:
            if annot['documentid'] not in annotationobj:
                annotationobj[annot['documentid']] = []
            annotationobj[annot['documentid']].append(annot["annotation"])
        for documentid in annotationobj:
            annotationobj[documentid] = annotationobj[documentid]
            # annotationobj[documentid] = self.__generateannotationsxml(annotationobj[documentid])
        return annotationobj

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
    
    def getrequestannotationinfo(self, ministryrequestid):
        annotationsections = AnnotationSection.getsectionmappingbyrequestid(ministryrequestid)
        for entry in annotationsections:
            entry['sections'] = {"annotationname": entry.pop("sectionannotation"), "ids": list(map(lambda id: id['id'], json.loads(entry.pop("ids"))))}            
        return annotationsections

    def getredactedsectionsbyrequest(self, ministryrequestid):
        return {'sections': AnnotationSection.getredactedsectionsbyrequest(ministryrequestid)}

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

    def saveannotation(self, annotationschema, userinfo):
        annots = self.__extractannotfromxml(annotationschema['xml'])
        print("\nannots::",annots)
        _redactionlayerid = self.__getredactionlayerid(annotationschema)
        if len(annots) < 1:
            return DefaultMethodResult(True,'No valid Annotations found', -1) 
        resp = Annotation.saveannotations(annots, _redactionlayerid, userinfo)
        if resp.success == True:
            if "sections" in annotationschema:
                sectionresponse = AnnotationSection.savesections(annots, annotationschema['sections']['foiministryrequestid'], userinfo)
                if not sectionresponse:
                    return DefaultMethodResult(False,'Failed to save Annotation Section', resp.identifier)
        else:
            return DefaultMethodResult(False,'Failed to save Annotation', resp.identifier)
        #Collect all existing IDS
        delete_annots = []
        self.__deleteannotations(delete_annots, _redactionlayerid, userinfo)
        return DefaultMethodResult(True,'Annotation successfully saved', resp.identifier)

    

    def deactivateannotation(self, annotationname, redactionlayerid, userinfo):
        return self.__deleteannotations([annotationname], redactionlayerid, userinfo)
    
    def __deleteannotations(self, annotationnames, redactionlayerid, userinfo):
        if annotationnames not in (None, []) and len(annotationnames) > 0:
            resp = Annotation.bulkdeleteannotations(annotationnames, redactionlayerid, userinfo)
            if resp.success == True:
                AnnotationSection.bulkdeletesections(annotationnames, userinfo)
            return resp
        return DefaultMethodResult(True,'No Annotations marked for delete', -1)

    def __getdateformat(self):
        return '%Y %b %d | %I:%M %p'

    def __extractannotfromxml(self, xmlstring):
        xml = parseString(xmlstring)
        annotations = xml.getElementsByTagName("annots")[0].childNodes
        annots = []
        for annot in annotations:
            if self.__isvalid(annot) == True:
                customdata = annot.getElementsByTagName("trn-custom-data")[0].getAttribute("bytes")
                customdatadict = json.loads(customdata)
                annots.append({
                    "name": annot.getAttribute("name"),
                    "page": annot.getAttribute("page"),
                    "xml": annot.toxml(),
                    "sectionsschema": SectionAnnotationSchema().loads(customdata),
                    "originalpageno": customdatadict['originalPageNo'],
                    "docid": customdatadict['docid'],
                    "docversion": customdatadict['docversion'],
                    "type": customdatadict['trn-redaction-type'],
                    "existingid": customdatadict['existingId'] if 'existingId' in customdatadict else None
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
    
    def __getredactionlayerid(self, annotationschema):
        if 'redactionlayerid' in annotationschema and annotationschema['redactionlayerid'] not in (None,''):
            return int(annotationschema['redactionlayerid'])
        else:
            return redactionlayerservice().getdefaultredactionlayerid()
        

    def __isvalid(self, annot):
        if annot is not None and annot.tagName == "redact":
            if annot.getAttribute('inreplyto') not in (None,''):
                return True
            return False
        return True

