"""Service for pdf generation."""
import base64
import json
import os
import re

import requests
#from reviewer_api.exceptions import BusinessException, Error


class cdogsapiservice:
    """cdogs api Service class."""
    
    # def __init__(self):
    #     self.access_token = self._get_access_token()

    def demomethod(self):
        print("demomethod!!!")
   
    def generate_pdf(self, template_hash_code, data, access_token):
        #access_token= self._get_access_token()
        print('\n\ntemplate_hash_code:',template_hash_code)
        request_body = {
            "options": {
                "cachereport": False,
                "convertTo": "pdf",
                "overwrite": True,
                "reportName": "Summary"
            },
            "data": data
        }
        json_request_body = json.dumps(request_body)
        print("\njson_request_body:",json_request_body)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        #url = f"{os.getenv['CDOGS_BASE_URL']}/api/v2/template/{template_hash_code}/render"
        url = f"https://cdogs-dev.api.gov.bc.ca/api/v2/template/{template_hash_code}/render"
        return self._post_generate_pdf(json_request_body, headers, url)

    def _post_generate_pdf(self, json_request_body, headers, url):
        return requests.post(url, data= json_request_body, headers= headers)

    def upload_template(self, receipt_template_path, access_token):
        print('\nreceipt_template_path:',receipt_template_path)
        #access_token= self._get_access_token()
        file_dir = os.path.dirname(os.path.realpath('__file__'))
        #print("file_dir:",file_dir)
        template_file_path = os.path.join(file_dir, receipt_template_path)
        #print("template_file_path:",template_file_path)
        headers = {
        "Authorization": f'Bearer {access_token}'
        }

        #url = f"{current_app.config['CDOGS_BASE_URL']}/api/v2/template"
        url = "https://cdogs-dev.api.gov.bc.ca/api/v2/template"
        
        if os.path.exists(receipt_template_path):
            print("@@@Exists!!")
        template = {'template':('template', open(receipt_template_path, 'rb'), "multipart/form-data")}
        print("\n\n1)url:",url)
        print('\n\n2)Uploading template %s', template)
        print("\n\n3)headers:",headers)
        response = self._post_upload_template(headers, url, template)
        print("\n\nRESPONSE from UPLOAD ->",response)
        if response.status_code == 200:
            # if response.headers.get("X-Template-Hash") is None:
            #     raise BusinessException(Error.DATA_NOT_FOUND)

            print('Returning new hash %s', response.headers['X-Template-Hash'])
            return response.headers['X-Template-Hash'];
    
        response_json = json.loads(response.content)
        
        if response.status_code == 405 and response_json['detail'] is not None:
            match = re.findall(r"Hash '(.*?)'", response_json['detail']);
            if match:
                print('Template already hashed with code %s', match[0])
                print('Template already hashed with code %s', match[0])
                return match[0]
            
        #raise BusinessException(Error.DATA_NOT_FOUND)

    def _post_upload_template(self, headers, url, template):
        response = requests.post(url, headers= headers, files= template)
        return response

    def check_template_cached(self, template_hash_code, access_token):

        headers = {
        "Authorization": f'Bearer {access_token}'
        }

        #url = f"{os.getenv['CDOGS_BASE_URL']}/api/v2/template/{template_hash_code}"
        url = f"https://cdogs-dev.api.gov.bc.ca/api/v2/template/{template_hash_code}"

        response = requests.get(url, headers= headers)
        return response.status_code == 200
        

    def _get_access_token(self):
        print("\n\n*********")
        #print("\n\nCDOGS_TOKEN_URL:",os.getenv['CDOGS_TOKEN_URL'])
        token_url = "https://dev.loginproxy.gov.bc.ca/auth/realms/comsvcauth/protocol/openid-connect/token" #os.getenv['CDOGS_TOKEN_URL']
        service_client = "906B4222-00D7D1A3339" #os.getenv['CDOGS_SERVICE_CLIENT']
        service_client_secret = "c7c94a59-bed6-4fc3-85ed-acc43161753e" #os.getenv['CDOGS_SERVICE_CLIENT_SECRET']
        print("token_url:",token_url)
        basic_auth_encoded = base64.b64encode(
            bytes(service_client + ':' + service_client_secret, 'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        print("basic_auth_encoded:",basic_auth_encoded)
        response = requests.post(
            token_url,
            data=data,
            headers={
                'Authorization': f'Basic {basic_auth_encoded}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )

        response_json = response.json()
        return response_json['access_token']