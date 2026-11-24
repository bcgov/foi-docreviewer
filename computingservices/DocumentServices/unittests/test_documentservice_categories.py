"""Summary category contracts with real schemas/orchestration and isolated external I/O."""
import importlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def summary_service(monkeypatch, real_service_modules):
    module = importlib.import_module('services.redactionsummaryservice')
    doc, foi = Mock(), Mock()
    monkeypatch.setattr(module, 'getdbconnection', lambda: doc)
    monkeypatch.setattr(module, 'getfoidbconnection', lambda: foi)
    monkeypatch.setattr(module.documenttemplate, 'getcompatibledocumentids', lambda ids: ids)
    monkeypatch.setattr(module.documentpageflag, 'get_all_pageflags', lambda *args, **kwargs: [])
    monkeypatch.setattr(module.documentpageflag, 'get_all_programareas', lambda *args, **kwargs: [])
    monkeypatch.setattr(module.redactionsummary, 'prepareredactionsummary', lambda *args, **kwargs: {'data': ['é 22']})
    statuses = []
    monkeypatch.setattr(module.pdfstitchjobactivity, 'recordjobstatus', lambda self, *args: statuses.append(args[1:]))
    return module, doc, foi, statuses


def message(category, code='edu', requesttype='general', phase=None):
    return {
        'jobid': 1, 'requestid': 1, 'ministryrequestid': 1, 'category': category,
        'requestnumber': 'SYNTHETIC-001', 'bcgovcode': code, 'createdby': 'synthetic',
        'filestozip': '[]', 'finaloutput': '{}',
        'attributes': json.dumps([{'divisionid': 3, 'divisionname': 'Éducation',
                                 'files': [{'s3uripath': f'https://synthetic/{category}/source.pdf', 'filename': 'source.pdf'}]}]),
        'summarydocuments': json.dumps({'sorteddocuments': [1], 'pkgdocuments': [{'divisionid': 3, 'documentids': [1]}]}),
        'redactionlayerid': 1, 'requesttype': requesttype, 'feeoverridereason': None,
        'phase': phase, 'documentsetid': None,
    }


@pytest.mark.parametrize('category,code,requesttype,phase,template,filename', [
    ('responsepackage', 'edu', 'general', None, 'responsepackage_redaction_summary', 'SYNTHETIC-001 - summary.pdf'),
    ('responsepackage', 'mcf', 'personal', None, 'CFD_responsepackage_redaction_summary', 'SYNTHETIC-001 - summary.pdf'),
    ('responsepackagephase', 'edu', 'general', '2', 'responsepackage_redaction_summary', 'SYNTHETIC-001 - Phase 2 - summary.pdf'),
    ('oipcreviewredline', 'edu', 'general', None, 'redline_redaction_summary', 'SYNTHETIC-001 - Redline - summary.pdf'),
    ('oipcreviewredline', 'edu', 'general', '2', 'redline_redaction_summary', 'SYNTHETIC-001 - Redline - Phase 2 - summary.pdf'),
    ('openinfo', 'edu', 'general', None, 'responsepackage_redaction_summary', 'Redaction_Summary_SYNTHETIC-001.pdf'),
])
def test_category_template_and_summary_filename(summary_service, monkeypatch, category, code, requesttype, phase, template, filename):
    module, doc, foi, statuses = summary_service
    def generate(self, data, name, path):
        assert data == {'data': ['é 22']}
        assert name == template
        assert path == f'templates/{template}.docx'
        return SimpleNamespace(content=b'%PDF synthetic')
    monkeypatch.setattr(module.documentgenerationservice, 'generate_pdf', generate)
    def upload(name, content, uri):
        assert name == filename
        assert content == b'%PDF synthetic'
        return {'filename': name, 'documentpath': uri + name, 'uploadresponse': SimpleNamespace(status_code=200)}
    monkeypatch.setattr(module, 'uploadbytes', upload)
    result = module.redactionsummaryservice().processmessage(json.dumps(message(category, code, requesttype, phase)))
    assert len(result) == 1
    assert result[0]['filename'] == filename
    assert statuses[-1] == (4, 'redactionsummaryuploaded', False, '')
    doc.close.assert_called_once()
    foi.close.assert_called_once()


def test_consult_bypasses_database_and_generation(summary_service):
    module, doc, foi, statuses = summary_service
    assert module.redactionsummaryservice().processmessage(json.dumps(message('consultpackage'))) == []
    doc.close.assert_not_called()
    foi.close.assert_not_called()
    assert statuses == []


@pytest.mark.parametrize('failure', ['database', 'render', 'upload', 'empty'])
def test_failure_and_empty_document_cleanup(summary_service, monkeypatch, failure):
    module, doc, foi, statuses = summary_service
    def fail(*args, **kwargs):
        raise RuntimeError('synthetic ' + failure)
    if failure == 'database':
        monkeypatch.setattr(module, 'getfoidbconnection', fail)
    elif failure == 'render':
        monkeypatch.setattr(module.documentgenerationservice, 'generate_pdf', fail)
    elif failure == 'upload':
        monkeypatch.setattr(module.documentgenerationservice, 'generate_pdf', lambda *args: SimpleNamespace(content=b'pdf'))
        monkeypatch.setattr(module, 'uploadbytes', fail)
    else:
        monkeypatch.setattr(module.documenttemplate, 'getcompatibledocumentids', lambda ids: [])
    assert module.redactionsummaryservice().processmessage(json.dumps(message('responsepackage'))) == []
    doc.close.assert_called_once()
    if failure != 'database':
        foi.close.assert_called_once()
    if failure != 'empty':
        assert statuses[-1][1] == 'redactionsummaryfailed'
