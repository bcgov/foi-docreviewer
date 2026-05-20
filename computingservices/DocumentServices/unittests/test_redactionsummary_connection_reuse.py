import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


DOCUMENT_PAGE_FLAG_PATH = Path(__file__).resolve().parents[1] / "services" / "dal" / "documentpageflag.py"
REDACTION_SUMMARY_PATH = Path(__file__).resolve().parents[1] / "services" / "dts" / "redactionsummary.py"


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.closed = False
        self.cursors = []

    def cursor(self):
        cursor = FakeCursor(self.rows)
        self.cursors.append(cursor)
        return cursor

    def close(self):
        self.closed = True


def load_documentpageflag_module(created_connections):
    module_name = "DocumentServices.services.dal.documentpageflag_connection_reuse_under_test"
    for name in [module_name, "utils"]:
        sys.modules.pop(name, None)

    def getdbconnection():
        conn = FakeConnection([(1, "Full Disclosure", "Full Disclosure")])
        created_connections.append(conn)
        return conn

    utils_module = types.ModuleType("utils")
    utils_module.getdbconnection = getdbconnection
    utils_module.getfoidbconnection = getdbconnection
    sys.modules["utils"] = utils_module

    spec = importlib.util.spec_from_file_location(module_name, DOCUMENT_PAGE_FLAG_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_redactionsummary_module(fake_documentpageflag):
    module_name = "DocumentServices.services.dts.redactionsummary_connection_reuse_under_test"
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


class DocumentPageFlagConnectionReuseTests(unittest.TestCase):
    def test_dal_does_not_close_caller_owned_connection(self):
        created_connections = []
        module = load_documentpageflag_module(created_connections)
        caller_conn = FakeConnection([(1, "Full Disclosure", "Full Disclosure")])

        result = module.documentpageflag.get_all_pageflags([], conn=caller_conn)

        self.assertEqual([{"pageflagid": 1, "name": "Full Disclosure", "description": "Full Disclosure"}], result)
        self.assertFalse(caller_conn.closed)
        self.assertEqual([], created_connections)

    def test_dal_closes_connection_it_creates(self):
        created_connections = []
        module = load_documentpageflag_module(created_connections)

        module.documentpageflag.get_all_pageflags([])

        self.assertEqual(1, len(created_connections))
        self.assertTrue(created_connections[0].closed)


class RedactionSummaryConnectionReuseTests(unittest.TestCase):
    def test_redactionsummary_uses_caller_document_connection_for_dal_calls(self):
        received_connections = []

        class FakeDocumentPageFlag:
            def getrecentredactionlayerid(self, ministryrequestid, conn=None):
                received_connections.append(conn)
                return 99

            def getpagecount_by_documentid(self, ministryrequestid, documentids, conn=None):
                received_connections.append(conn)
                return {10: {"pagecount": 1}}

            def getoriginalpagecount_by_documentid(self, ministryrequestid, documentids, conn=None):
                received_connections.append(conn)
                return {10: {"pagecount": 1}}

            def get_documentpageflag(self, ministryrequestid, redactionlayerid, documentids, conn=None):
                received_connections.append(conn)
                return {10: {"pageflag": [{"page": 1, "flagid": 1}], "attributes": {}}}

            def getdeletedpages(self, ministryrequestid, docids, conn=None):
                received_connections.append(conn)
                return []

            def getsections_by_documentid_pageno(self, redactionlayerid, documentid, pagenos, conn=None):
                received_connections.append(conn)
                return [{"pageno": 0, "section": "22"}]

        module = load_redactionsummary_module(FakeDocumentPageFlag)
        sentinel_conn = object()
        message = types.SimpleNamespace(
            bcgovcode="EDU",
            requesttype="general",
            category="responsepackage",
            ministryrequestid=500,
            requestnumber="EDU-2026-0001",
            redactionlayerid=7,
            phase=None,
            summarydocuments=json.dumps({"sorteddocuments": [10], "pkgdocuments": []}),
        )

        module.redactionsummary().prepareredactionsummary(
            message,
            [10],
            [{"pageflagid": 1, "name": "Full Disclosure", "description": "Full Disclosure"}],
            {},
            doc_conn=sentinel_conn,
        )

        self.assertEqual(5, len(received_connections))
        self.assertTrue(all(conn is sentinel_conn for conn in received_connections))


if __name__ == "__main__":
    unittest.main()
