import json
import uuid
import os
import requests
import ast

TEST_INTAKE_USER_PAYLOAD = {
    'client_id': 'forms-flow-web',
    'grant_type': 'password',
    'username' : os.getenv('TEST_INTAKE_USERID'),
    'password': os.getenv('TEST_INTAKE_PASSWORD')
}

TEST_MINISTRY_USER_PAYLOAD = {
    'client_id': 'forms-flow-web',
    'grant_type': 'password',
    'username' : os.getenv('TEST_MINISTRY_USERID'),
    'password': os.getenv('TEST_MINISTRY_PASSWORD')
}

TEST_ANNOTATION_SCHEMA = {
    "xml": '''<?xml version="1.0" encoding="UTF-8" ?><xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve"><annots><underline page="1" rect="58.872,645.038,162.996,656.538" color="#E44234" flags="print" name="eb19ce33-dab1-1520-386d-3ff9dafda573" title="Super User" subject="Underline" date="D:20221114122116-08'00'" creationdate="D:20221114122116-08'00'" coords="58.872,656.538105859375,162.996,656.538105859375,58.872,645.03835,162.996,645.03835"><trn-custom-data bytes="{&quot;trn-annot-preview&quot;:&quot;commercial PDF SD&quot;}"/></underline></annots></xfdf>'''
}


# RAW_REQUEST_JSON = 'tests/samplerequestjson/rawrequest.json'
# FOI_REQUEST_GENERAL_JSON = 'tests/samplerequestjson/foirequest-general.json'
# FOI_REQUEST_GENERAL_UPDATE_JSON = 'tests/samplerequestjson/foirequest-general-update.json'
# FOI_REQUEST_GENERAL_MINISTRY_UPDATE_JSON = 'tests/samplerequestjson/foirequest-ministry-general-update.json'
DOCUMENT_API_URL = '/api/document/'
REDACTION_API_URL = '/api/annotation/'

CONTENT_TYPE = 'application/json'

def factory_intake_auth_header(app, client):
    url = '{0}/auth/realms/{1}/protocol/openid-connect/token'.format(os.getenv('KEYCLOAK_ADMIN_HOST'),os.getenv('KEYCLOAK_ADMIN_REALM'))        
    x = requests.post(url, TEST_INTAKE_USER_PAYLOAD, verify=True).content.decode('utf-8')       
    return {'Authorization': 'Bearer ' + str(ast.literal_eval(x)['access_token'])}  

def factory_ministry_auth_header(app, client):
    url = '{0}/auth/realms/{1}/protocol/openid-connect/token'.format(os.getenv('KEYCLOAK_ADMIN_HOST'),os.getenv('KEYCLOAK_ADMIN_REALM'))        
    x = requests.post(url, TEST_MINISTRY_USER_PAYLOAD, verify=True).content.decode('utf-8')       
    return {'Authorization': 'Bearer ' + str(ast.literal_eval(x)['access_token'])}  

def test_ping(app, client):
    response = client.get('/api/healthz')
    assert response.status_code == 200

def test_document_list(app, client):
    ministryrequestid = "1"
    getdocumentsresponse = client.get(DOCUMENT_API_URL+ministryrequestid, headers=factory_ministry_auth_header(app, client), content_type=CONTENT_TYPE)
    assert getdocumentsresponse.status_code == 200

def test_annotation_create(app, client):  
    documentid = "1"
    documentversion = "1"
    pagenumber = "1"
    annotationname = "test123"
    posturl = REDACTION_API_URL+documentid+'/'+documentversion+'/'+pagenumber+'/'+annotationname
    annotationresponse = client.post(posturl, data=json.dumps(TEST_ANNOTATION_SCHEMA), headers=factory_intake_auth_header(app, client), content_type=CONTENT_TYPE)
    assert annotationresponse.status_code == 201
