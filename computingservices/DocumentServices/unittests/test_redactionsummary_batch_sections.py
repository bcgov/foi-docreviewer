import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


REDACTION_SUMMARY_PATH = Path(__file__).resolve().parents[1] / "services" / "dts" / "redactionsummary.py"
DOCUMENT_PAGE_FLAG_PATH = Path(__file__).resolve().parents[1] / "services" / "dal" / "documentpageflag.py"


def _load_redactionsummary_module(fake_documentpageflag):
    module_name = "DocumentServices.services.dts.redactionsummary_batch_under_test"

    for name in [
        module_name,
        "services",
        "services.dal",
        "services.dal.documentpageflag",
        "rstreamio",
        "rstreamio.message",
        "rstreamio.message.schemas",
        "rstreamio.message.schemas.redactionsummary",
    ]:
        sys.modules.pop(name, None)

    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = []
    sys.modules["services"] = services_pkg

    services_dal_pkg = types.ModuleType("services.dal")
    services_dal_pkg.__path__ = []
    sys.modules["services.dal"] = services_dal_pkg

    documentpageflag_module = types.ModuleType("services.dal.documentpageflag")
    documentpageflag_module.documentpageflag = fake_documentpageflag
    sys.modules["services.dal.documentpageflag"] = documentpageflag_module

    rstreamio_pkg = types.ModuleType("rstreamio")
    rstreamio_pkg.__path__ = []
    sys.modules["rstreamio"] = rstreamio_pkg

    message_pkg = types.ModuleType("rstreamio.message")
    message_pkg.__path__ = []
    sys.modules["rstreamio.message"] = message_pkg

    schemas_pkg = types.ModuleType("rstreamio.message.schemas")
    schemas_pkg.__path__ = []
    sys.modules["rstreamio.message.schemas"] = schemas_pkg

    schema_module = types.ModuleType("rstreamio.message.schemas.redactionsummary")
    schema_module.get_in_summary_object = lambda payload: types.SimpleNamespace(**json.loads(payload))
    schema_module.get_in_summarypackage_object = lambda payload: types.SimpleNamespace(**json.loads(payload))
    sys.modules["rstreamio.message.schemas.redactionsummary"] = schema_module

    spec = importlib.util.spec_from_file_location(module_name, REDACTION_SUMMARY_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_documentpageflag_module(fake_connection):
    module_name = "DocumentServices.services.dal.documentpageflag_batch_under_test"

    for name in [
        module_name,
        "utils",
    ]:
        sys.modules.pop(name, None)

    utils_module = types.ModuleType("utils")
    utils_module.getdbconnection = lambda: fake_connection
    utils_module.getfoidbconnection = lambda: fake_connection
    sys.modules["utils"] = utils_module

    spec = importlib.util.spec_from_file_location(module_name, DOCUMENT_PAGE_FLAG_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class RedactionSummaryBatchSectionTests(unittest.TestCase):
    def test_getsections_batch_uses_annotation_type_and_exact_document_page_pairs(self):
        class FakeCursor:
            executed_sql = None
            executed_params = None

            def execute(self, sql, params):
                type(self).executed_sql = sql
                type(self).executed_params = params

            def fetchall(self):
                return [(10, 0, "22, 15"), (20, 2, "13")]

            def close(self):
                return None

        class FakeConnection:
            closed = False

            def cursor(self):
                return FakeCursor()

            def close(self):
                type(self).closed = True

        module = _load_documentpageflag_module(FakeConnection())

        sections = module.documentpageflag.getsections_batch(99, {10: [1, 0, 0], 20: [2]})

        self.assertEqual(
            [
                {"documentid": 10, "pageno": 0, "section": "22, 15"},
                {"documentid": 20, "pageno": 2, "section": "13"},
            ],
            sections,
        )
        self.assertIn("a.annotationtype = 'freetext'", FakeCursor.executed_sql)
        self.assertNotIn("annotation LIKE", FakeCursor.executed_sql)
        self.assertIn("unnest(%s::integer[], %s::integer[])", FakeCursor.executed_sql)
        self.assertEqual(([10, 10, 20], [0, 1, 2], 99), FakeCursor.executed_params)

    def test_assignfullpagesections_uses_one_batch_query_for_all_documents(self):
        class FakeDocumentPageFlag:
            batch_calls = []
            single_calls = []

            def getsections_batch(self, redactionlayerid, document_pages, conn=None):
                type(self).batch_calls.append((redactionlayerid, document_pages))
                return [
                    {"documentid": 10, "pageno": 0, "section": "22, 15"},
                    {"documentid": 20, "pageno": 2, "section": "13"},
                ]

            def getsections_by_documentid_pageno(self, redactionlayerid, documentid, pagenos, conn=None):
                type(self).single_calls.append((redactionlayerid, documentid, pagenos))
                return []

        module = _load_redactionsummary_module(FakeDocumentPageFlag)
        summary = module.redactionsummary()
        mapped_flags = [
            {"docid": 10, "dbpageno": 0, "originalpageno": 1, "stitchedpageno": 1, "flagid": 3},
            {"docid": 10, "dbpageno": 1, "originalpageno": 2, "stitchedpageno": 2, "flagid": 4},
            {"docid": 20, "dbpageno": 2, "originalpageno": 3, "stitchedpageno": 3, "flagid": 3},
        ]

        summary.assignfullpagesections(99, mapped_flags)

        self.assertEqual([(99, {10: [0, 1], 20: [2]})], FakeDocumentPageFlag.batch_calls)
        self.assertEqual([], FakeDocumentPageFlag.single_calls)
        self.assertEqual(["22", "15"], mapped_flags[0]["sections"])
        self.assertNotIn("sections", mapped_flags[1])
        self.assertEqual(["13"], mapped_flags[2]["sections"])

    def test_mcf_personal_summary_assigns_full_page_sections_once(self):
        class FakeDocumentPageFlag:
            def getrecentredactionlayerid(self, ministryrequestid, conn=None):
                return 99

            def getpagecount_by_documentid(self, ministryrequestid, documentids, conn=None):
                return {10: {"pagecount": 1}, 20: {"pagecount": 1}}

            def get_documentpageflag(self, ministryrequestid, redactionlayerid, documentids, conn=None):
                return {
                    10: {"pageflag": [{"page": 1, "flagid": 3}], "attributes": {}},
                    20: {"pageflag": [{"page": 1, "flagid": 3}], "attributes": {}},
                }

            def getdeletedpages(self, ministryrequestid, docids, conn=None):
                return []

        module = _load_redactionsummary_module(FakeDocumentPageFlag)

        class CountingRedactionSummary(module.redactionsummary):
            assign_calls = 0

            def assignfullpagesections(self, redactionlayerid, mapped_flags, doc_conn=None):
                type(self).assign_calls += 1
                for flag in mapped_flags:
                    if flag["flagid"] == 3:
                        flag["sections"] = ["22"]

        message = types.SimpleNamespace(
            bcgovcode="mcf",
            requesttype="personal",
            category="responsepackage",
            ministryrequestid=500,
            requestnumber="MCF-2026-0001",
            phase=None,
            summarydocuments=json.dumps(
                {
                    "sorteddocuments": [10, 20],
                    "pkgdocuments": [
                        {
                            "records": [
                                {"recordname": "record a", "documentids": [10]},
                                {"recordname": "record b", "documentids": [20]},
                            ]
                        }
                    ],
                }
            ),
        )

        result = CountingRedactionSummary().prepareredactionsummary(message, [10, 20], [], {})

        self.assertEqual(1, CountingRedactionSummary.assign_calls)
        self.assertEqual("MCF-2026-0001", result["requestnumber"])


if __name__ == "__main__":
    unittest.main()
