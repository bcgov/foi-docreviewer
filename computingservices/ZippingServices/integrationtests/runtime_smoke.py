"""Run as app_user in the production image before installing test dependencies."""
import importlib
import os
import sys

assert sys.version_info[:2] == (3, 13), sys.version
assert os.getuid() != 0
print(sys.version)
print(open('/etc/os-release').read())
for name in ('psycopg2', 'redis', 'walrus', 'PyPDF2', 'pypdf', 'reportlab', 'wrapt',
             'requests', 'aws_requests_auth', 'marshmallow', 'boto3', 'botocore', 's3transfer'):
    module = importlib.import_module(name)
    print(name, getattr(module, '__version__', 'imported'))
from walrus import Database
from redis import Redis
from aws_requests_auth.aws_auth import AWSRequestsAuth
import requests
assert isinstance(Database(), Redis)
request = requests.Request('GET', 'https://example.invalid/synthetic', auth=AWSRequestsAuth(
    aws_access_key='synthetic', aws_secret_access_key='synthetic', aws_host='example.invalid',
    aws_region='us-east-1', aws_service='s3')).prepare()
assert request.headers['Authorization'].startswith('AWS4-HMAC-SHA256 ')
print('Fresh imports, Walrus construction and AWS request signing passed')
