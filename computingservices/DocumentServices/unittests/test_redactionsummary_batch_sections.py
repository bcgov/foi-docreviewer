import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

from unittests.redactionsummary_test_utils import load_redactionsummary_module

DOCUMENT_PAGE_FLAG_PATH = Path(__file__).resolve().parents[1] / "services" / "dal" / "documentpageflag.py"


def _load_redactionsummary_module(fake_documentpageflag):
    return load_redactionsummary_module(
        "DocumentServices.services.dts.redactionsummary_batch_under_test",
        fake_documentpageflag,
    )


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

    def test_non_mcf_responsepackage_uses_one_batch_section_query(self):
        class FakeDocumentPageFlag:
            batch_calls = []
            single_calls = []

            def getrecentredactionlayerid(self, ministryrequestid, conn=None):
                return 99

            def getpagecount_by_documentid(self, ministryrequestid, documentids, conn=None):
                return {
                    10: {"pagecount": 2},
                    20: {"pagecount": 2},
                }

            def get_documentpageflag(self, ministryrequestid, redactionlayerid, documentids, conn=None):
                return {
                    10: {
                        "pageflag": [
                            {"page": 1, "flagid": 1},
                            {"page": 2, "flagid": 2},
                        ],
                        "attributes": {},
                    },
                    20: {
                        "pageflag": [
                            {"page": 1, "flagid": 1},
                            {"page": 2, "flagid": 2},
                        ],
                        "attributes": {},
                    },
                }

            def getdeletedpages(self, ministryrequestid, docids, conn=None):
                return []

            def getsections_batch(self, redactionlayerid, document_pages, conn=None):
                type(self).batch_calls.append((redactionlayerid, document_pages, conn))
                return [
                    {"documentid": 10, "pageno": 0, "section": "22"},
                    {"documentid": 10, "pageno": 1, "section": "15"},
                    {"documentid": 20, "pageno": 0, "section": "13"},
                    {"documentid": 20, "pageno": 1, "section": "21"},
                ]

            def getsections_by_documentid_pageno(self, redactionlayerid, documentid, pagenos, conn=None):
                type(self).single_calls.append((redactionlayerid, documentid, pagenos, conn))
                return []

        module = _load_redactionsummary_module(FakeDocumentPageFlag)
        message = types.SimpleNamespace(
            bcgovcode="EDU",
            requesttype="general",
            category="responsepackage",
            ministryrequestid=500,
            requestnumber="EDU-2026-0001",
            redactionlayerid=7,
            phase=None,
            summarydocuments=json.dumps(
                {
                    "sorteddocuments": [10, 20],
                    "pkgdocuments": [{"divisionid": 1, "documentids": [10, 20]}],
                }
            ),
        )
        pageflags = [
            {"pageflagid": 1, "name": "Full Disclosure", "description": "Full Disclosure"},
            {"pageflagid": 2, "name": "Partial Disclosure", "description": "Partial Disclosure"},
        ]
        doc_conn = object()

        result = module.redactionsummary().prepareredactionsummary(
            message, [10, 20], pageflags, {}, doc_conn=doc_conn
        )

        self.assertEqual([(99, {10: [0, 1], 20: [0, 1]}, doc_conn)], FakeDocumentPageFlag.batch_calls)
        self.assertEqual([], FakeDocumentPageFlag.single_calls)
        self.assertEqual("EDU-2026-0001", result["requestnumber"])
        self.assertEqual(4, len(result["data"]))

    def test_batched_pagesections_are_indexed_by_page_before_mapping(self):
        class FakeDocumentPageFlag:
            def getsections_batch(self, redactionlayerid, document_pages, conn=None):
                return [
                    {"documentid": 10, "pageno": 0, "section": "22"},
                    {"documentid": 10, "pageno": 0, "section": "15"},
                    {"documentid": 10, "pageno": 1, "section": "13"},
                ]

        module = _load_redactionsummary_module(FakeDocumentPageFlag)
        summary = module.redactionsummary()

        def fail_if_linear_scan_is_used(*args, **kwargs):
            raise AssertionError("batched section mapping should use a page index")

        summary._redactionsummary__get_sections = fail_if_linear_scan_is_used
        pageflag = {"docpageflags": []}
        pending_mappings = [
            {
                "docid": 10,
                "pageflag": pageflag,
                "filteredpages": [
                    {"originalpageno": 0, "stitchedpageno": 1},
                    {"originalpageno": 1, "stitchedpageno": 2},
                    {"originalpageno": 2, "stitchedpageno": 3},
                ],
                "docpageconsults": {1: "IAO"},
            }
        ]

        summary._redactionsummary__assign_batched_pagesections(
            99,
            {10: [0, 1, 2]},
            pending_mappings,
        )

        self.assertEqual(
            [
                {
                    "originalpageno": 0,
                    "stitchedpageno": 1,
                    "sections": ["22", "15"],
                    "consults": None,
                },
                {
                    "originalpageno": 1,
                    "stitchedpageno": 2,
                    "sections": ["13"],
                    "consults": "IAO",
                },
                {
                    "originalpageno": 2,
                    "stitchedpageno": 3,
                    "sections": [],
                    "consults": None,
                },
            ],
            pageflag["docpageflags"],
        )


if __name__ == "__main__":
    unittest.main()
