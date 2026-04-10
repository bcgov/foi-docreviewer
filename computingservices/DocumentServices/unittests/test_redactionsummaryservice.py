import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


SERVICE_PATH = Path(__file__).resolve().parents[1] / "services" / "redactionsummaryservice.py"


def _load_service_module():
    module_name = "DocumentServices.services.redactionsummaryservice_under_test"

    for name in [
        module_name,
        "DocumentServices",
        "DocumentServices.services",
        "services",
        "services.dal",
        "services.dts",
        "rstreamio",
        "rstreamio.message",
        "rstreamio.message.schemas",
    ]:
        sys.modules.pop(name, None)

    documentservices_pkg = types.ModuleType("DocumentServices")
    documentservices_pkg.__path__ = []
    sys.modules["DocumentServices"] = documentservices_pkg

    documentservices_services_pkg = types.ModuleType("DocumentServices.services")
    documentservices_services_pkg.__path__ = []
    sys.modules["DocumentServices.services"] = documentservices_services_pkg

    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = []
    sys.modules["services"] = services_pkg

    services_dal_pkg = types.ModuleType("services.dal")
    services_dal_pkg.__path__ = []
    sys.modules["services.dal"] = services_dal_pkg

    services_dts_pkg = types.ModuleType("services.dts")
    services_dts_pkg.__path__ = []
    sys.modules["services.dts"] = services_dts_pkg

    rstreamio_pkg = types.ModuleType("rstreamio")
    rstreamio_pkg.__path__ = []
    sys.modules["rstreamio"] = rstreamio_pkg

    rstreamio_message_pkg = types.ModuleType("rstreamio.message")
    rstreamio_message_pkg.__path__ = []
    sys.modules["rstreamio.message"] = rstreamio_message_pkg

    rstreamio_schemas_pkg = types.ModuleType("rstreamio.message.schemas")
    rstreamio_schemas_pkg.__path__ = []
    sys.modules["rstreamio.message.schemas"] = rstreamio_schemas_pkg

    pdfstitch_module = types.ModuleType("services.dal.pdfstitchjobactivity")

    class FakePdfStitchJobActivity:
        def recordjobstatus(self, *args, **kwargs):
            return None

    pdfstitch_module.pdfstitchjobactivity = FakePdfStitchJobActivity
    sys.modules["services.dal.pdfstitchjobactivity"] = pdfstitch_module

    redactionsummary_module = types.ModuleType("services.dts.redactionsummary")

    class FakeRedactionSummary:
        calls = []

        def prepareredactionsummary(self, message, documentids, pageflags, programareas):
            type(self).calls.append(list(documentids))
            return {"requestnumber": message.requestnumber, "data": []}

    redactionsummary_module.redactionsummary = FakeRedactionSummary
    sys.modules["services.dts.redactionsummary"] = redactionsummary_module

    documentgeneration_module = types.ModuleType("DocumentServices.services.documentgenerationservice")

    class FakeGeneratedPdf:
        content = b"pdf"

    class FakeDocumentGenerationService:
        def generate_pdf(self, *args, **kwargs):
            return FakeGeneratedPdf()

    documentgeneration_module.documentgenerationservice = FakeDocumentGenerationService
    sys.modules["DocumentServices.services.documentgenerationservice"] = documentgeneration_module

    s3document_module = types.ModuleType("DocumentServices.services.s3documentservice")

    class FakeUploadResponse:
        status_code = 200
        text = ""

    def fake_uploadbytes(filename, content, s3uri):
        return {
            "filename": filename,
            "documentpath": f"{s3uri}{filename}",
            "uploadresponse": FakeUploadResponse(),
        }

    s3document_module.uploadbytes = fake_uploadbytes
    sys.modules["DocumentServices.services.s3documentservice"] = s3document_module

    documentpageflag_module = types.ModuleType("services.dal.documentpageflag")

    class FakeDocumentPageFlag:
        def get_all_pageflags(self, *args, **kwargs):
            return []

        def get_all_programareas(self, *args, **kwargs):
            return []

    documentpageflag_module.documentpageflag = FakeDocumentPageFlag
    sys.modules["services.dal.documentpageflag"] = documentpageflag_module

    documenttemplate_module = types.ModuleType("services.dal.documenttemplate")

    class FakeDocumentTemplate:
        compatible_document_ids = []
        record_group_document_ids = []
        compatible_calls = []
        record_group_calls = []

        @classmethod
        def getcompatibledocumentids(cls, document_ids):
            cls.compatible_calls.append(list(document_ids))
            return list(cls.compatible_document_ids)

        @classmethod
        def getrecordgroupsbyrequestid(cls, request_id, document_ids):
            cls.record_group_calls.append((request_id, list(document_ids)))
            return list(cls.record_group_document_ids)

    documenttemplate_module.documenttemplate = FakeDocumentTemplate
    sys.modules["services.dal.documenttemplate"] = documenttemplate_module

    schema_module = types.ModuleType("rstreamio.message.schemas.redactionsummary")

    def _as_object(payload):
        return types.SimpleNamespace(**json.loads(payload))

    schema_module.get_in_redactionsummary_msg = _as_object
    schema_module.get_in_summary_object = _as_object
    schema_module.get_in_summarypackage_object = _as_object
    sys.modules["rstreamio.message.schemas.redactionsummary"] = schema_module

    spec = importlib.util.spec_from_file_location(module_name, SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module, FakeDocumentTemplate, FakeRedactionSummary


class RedactionSummaryServiceTests(unittest.TestCase):
    def setUp(self):
        self.module, self.documenttemplate, self.redactionsummary = _load_service_module()
        self.documenttemplate.compatible_document_ids = []
        self.documenttemplate.record_group_document_ids = []
        self.documenttemplate.compatible_calls = []
        self.documenttemplate.record_group_calls = []
        self.redactionsummary.calls = []

    def test_filters_non_document_set_ids_before_generating_summary(self):
        self.documenttemplate.compatible_document_ids = [102432, 102439]
        message = {
            "jobid": 1,
            "requestid": 1,
            "ministryrequestid": 520,
            "category": "responsepackage",
            "requestnumber": "EDU-2023-04040757",
            "bcgovcode": "EDU",
            "createdby": "foiedu@idir",
            "filestozip": [],
            "finaloutput": {},
            "attributes": json.dumps([{
                "divisionname": "Learning and Education Programs",
                "divisionid": 3,
                "files": [{"s3uripath": "https://example/bucket/responsepackage/source.pdf", "filename": "source.pdf"}],
            }]),
            "summarydocuments": json.dumps({
                "sorteddocuments": [102432, 102433, 102439],
                "pkgdocuments": [{"divisionid": 3, "documentids": [102432, 102433, 102439]}],
            }),
            "redactionlayerid": 1,
            "requesttype": "general",
            "feeoverridereason": None,
            "phase": None,
            "documentsetid": None,
        }

        service = self.module.redactionsummaryservice()
        service.processmessage(json.dumps(message))

        self.assertEqual([[102432, 102439]], self.redactionsummary.calls)
        self.assertEqual([[102432, 102433, 102439]], self.documenttemplate.compatible_calls)
        self.assertEqual([], self.documenttemplate.record_group_calls)


if __name__ == "__main__":
    unittest.main()
