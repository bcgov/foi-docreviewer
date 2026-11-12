"""Characterize real CDOGS serialization and template selection at HTTP/DB boundaries."""
import importlib
import json
from types import SimpleNamespace

import pytest


@pytest.mark.usefixtures('real_service_modules')
@pytest.mark.parametrize('stored_hash,cached', [(None, False), ('old-hash', False), ('old-hash', True)])
@pytest.mark.parametrize('type_id', [None, 7])
def test_template_cache_upload_and_pdf_response(monkeypatch, stored_hash, cached, type_id):
    module = importlib.import_module('services.documentgenerationservice')
    api = importlib.import_module('services.cdogsapiservice')
    monkeypatch.setattr(api, 'cdogs_base_url', 'https://cdogs.example')
    monkeypatch.setattr(api, 'cdogs_token_url', 'https://token.example')
    monkeypatch.setattr(api, 'cdogs_service_client', 'test-client')
    monkeypatch.setattr(api, 'cdogs_service_client_secret', 'test-secret')
    monkeypatch.setattr(module.documenttemplate, 'getdocumenttypebyname', lambda self, name: type_id)
    monkeypatch.setattr(module.documenttemplate, 'gettemplatebytype', lambda self, ident: stored_hash)
    updates = []
    monkeypatch.setattr(module.documenttemplate, 'updatecdogshashcode', lambda self, ident, value: updates.append((ident, value)))
    payload = {'requestnumber': 'SYNTHETIC-001', 'data': [{'section': 'é — 22'}]}
    rendered = SimpleNamespace(status_code=200, content=b'%PDF-1.4 synthetic', text='')
    requests_seen = []
    expected_hash = 'old-hash' if type_id and stored_hash and cached else 'uploaded-hash'

    def post(url, **kwargs):
        requests_seen.append(url)
        if url == 'https://token.example':
            assert kwargs['data'] == 'grant_type=client_credentials'
            return SimpleNamespace(json=lambda: {'access_token': 'test-token'})
        assert kwargs['headers']['Authorization'] == 'Bearer test-token'
        if url.endswith('/api/v2/template'):
            template = kwargs['files']['template'][1]
            assert template.name == 'templates/CFD_responsepackage_redaction_summary.docx'
            assert template.read().startswith(b'PK')
            template.close()
            return SimpleNamespace(status_code=200, headers={'X-Template-Hash': 'uploaded-hash'})
        assert url == f'https://cdogs.example/api/v2/template/{expected_hash}/render'
        assert json.loads(kwargs['data']) == {
            'options': {'cachereport': False, 'convertTo': 'pdf', 'overwrite': True, 'reportName': 'Summary'},
            'data': payload,
        }
        return rendered

    def get(url, **kwargs):
        assert url == 'https://cdogs.example/api/v2/template/old-hash'
        assert kwargs['headers']['Authorization'] == 'Bearer test-token'
        return SimpleNamespace(status_code=200 if cached else 404)

    monkeypatch.setattr(api.requests, 'post', post)
    monkeypatch.setattr(api.requests, 'get', get)
    result = module.documentgenerationservice().generate_pdf(
        payload, 'CFD_responsepackage_redaction_summary', 'templates/CFD_responsepackage_redaction_summary.docx')
    assert result.content == b'%PDF-1.4 synthetic'
    assert ('https://cdogs.example/api/v2/template' in requests_seen) == (expected_hash == 'uploaded-hash')
    assert updates == ([(7, 'uploaded-hash')] if type_id and expected_hash == 'uploaded-hash' else [])


@pytest.mark.usefixtures('real_service_modules')
@pytest.mark.parametrize('failure', ['token', 'render'])
def test_token_and_render_failures_propagate(monkeypatch, failure):
    module = importlib.import_module('services.documentgenerationservice')
    monkeypatch.setattr(module.documenttemplate, 'getdocumenttypebyname', lambda self, name: 7)
    monkeypatch.setattr(module.documenttemplate, 'gettemplatebytype', lambda self, ident: 'cached')
    api = module.cdogsapiservice
    if failure == 'token':
        def token(self):
            raise RuntimeError('token unavailable')
        monkeypatch.setattr(api, '_get_access_token', token)
    else:
        monkeypatch.setattr(api, '_get_access_token', lambda self: 'token')
        monkeypatch.setattr(api, 'check_template_cached', lambda *args: True)
        monkeypatch.setattr(api, '_post_generate_pdf', lambda *args: SimpleNamespace(status_code=503, text='render unavailable'))
    with pytest.raises(Exception, match='token unavailable|PDF generation failed. Status: 503'):
        module.documentgenerationservice().generate_pdf({'data': []})
