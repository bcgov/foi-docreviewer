"""Service for pdf generation."""
import base64
import json
import os
import re

import requests
from utils.foidocumentserviceconfig import cdogs_base_url,cdogs_token_url,cdogs_service_client,cdogs_service_client_secret


class cdogsapiservice:
    """cdogs api Service class."""
    
   
    def generate_pdf(self, template_hash_code, data, access_token):
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
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        url = f"{cdogs_base_url}/api/v2/template/{template_hash_code}/render"
        return self._post_generate_pdf(json_request_body, headers, url)

    def _post_generate_pdf(self, json_request_body, headers, url):
        return requests.post(url, data= json_request_body, headers= headers)

    def upload_template(self, template_path, access_token):
        headers = {
        "Authorization": f'Bearer {access_token}'
        }
        url = f"{cdogs_base_url}/api/v2/template"
        if os.path.exists(template_path):
            print("Exists!!")
        template = {'template':('template', open(template_path, 'rb'), "multipart/form-data")}
        response = self._post_upload_template(headers, url, template)
        if response.status_code == 200:
            print('Returning new hash %s', response.headers['X-Template-Hash'])
            return response.headers['X-Template-Hash'];
    
        response_json = json.loads(response.content)
        if response.status_code == 405 and response_json['detail'] is not None:
            match = re.findall(r"Hash '(.*?)'", response_json['detail']);
            if match:
                print('Template already hashed with code %s', match[0])
                return match[0]
            

    def _post_upload_template(self, headers, url, template):
        response = requests.post(url, headers= headers, files= template)
        return response

    def check_template_cached(self, template_hash_code, access_token):

        headers = {
        "Authorization": f'Bearer {access_token}'
        }
        url = f"{cdogs_base_url}/api/v2/template/{template_hash_code}"
        response = requests.get(url, headers= headers)
        return response.status_code == 200
        

    def _get_access_token(self):
        token_url = cdogs_token_url
        service_client = cdogs_service_client
        service_client_secret = cdogs_service_client_secret
        basic_auth_encoded = base64.b64encode(
            bytes(service_client + ':' + service_client_secret, 'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
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