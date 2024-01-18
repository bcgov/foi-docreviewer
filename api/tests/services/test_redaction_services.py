import pytest
from reviewer_api.services.radactionservice import redactionservice
import json

def test_get_documents(session): 
      requestid = 1
      queue = redactionservice().getdocuments(requestid)
      assert len(queue) > 0

def test_save_annotation(session):
      annotationname = 'test123'
      documentid = 1
      documentversion = 1
      xml = '''<?xml version="1.0" encoding="UTF-8" ?><xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve"><annots><underline page="1" rect="58.872,645.038,162.996,656.538" color="#E44234" flags="print" name="eb19ce33-dab1-1520-386d-3ff9dafda573" title="Super User" subject="Underline" date="D:20221114122116-08'00'" creationdate="D:20221114122116-08'00'" coords="58.872,656.538105859375,162.996,656.538105859375,58.872,645.03835,162.996,645.03835"><trn-custom-data bytes="{&quot;trn-annot-preview&quot;:&quot;commercial PDF SD&quot;}"/></underline></annots></xfdf>'''
      pagenumber = 1
      userinfo = {"userid": "foisuper@idir", "firstname": "Super", "lastname": "User", "operatingteam": "processing"}
      response = redactionservice().saveannotation(annotationname, documentid, documentversion, xml, pagenumber, userinfo)
      requestid = response.identifier
      pytest.approxrequestidtoupdate = requestid    
      assert response.success == True


def test_deactive_annotation(session):
      annotationname = 'test123'
      documentid = 1
      documentversion = 1
      userinfo = {"userid": "foisuper@idir", "firstname": "Super", "lastname": "User", "operatingteam": "processing"}
      response = redactionservice().deactivateannotation(annotationname, documentid, documentversion, userinfo)
      requestid = response.identifier
      pytest.approxrequestidtoupdate = requestid    
      assert response.success == True