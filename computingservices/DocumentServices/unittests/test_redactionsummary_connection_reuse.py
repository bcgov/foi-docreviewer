import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

from unittests.redactionsummary_test_utils import load_redactionsummary_module as load_redactionsummary_with_fake_dal


DOCUMENT_PAGE_FLAG_PATH = Path(__file__).resolve().parents[1] / "services" / "dal" / "documentpageflag.py"


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
    return load_redactionsummary_with_fake_dal(
        "DocumentServices.services.dts.redactionsummary_connection_reuse_under_test",
        fake_documentpageflag,
    )


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

    def test_getrecentredactionlayerid_returns_scalar_from_cursor_row(self):
        created_connections = []
        module = load_documentpageflag_module(created_connections)
        caller_conn = FakeConnection([(42,)])

        result = module.documentpageflag.getrecentredactionlayerid(500, conn=caller_conn)

        self.assertEqual(42, result)
        self.assertFalse(caller_conn.closed)

    def test_getrecentredactionlayerid_defaults_when_no_row_returned(self):
        created_connections = []
        module = load_documentpageflag_module(created_connections)
        caller_conn = FakeConnection([])

        result = module.documentpageflag.getrecentredactionlayerid(500, conn=caller_conn)

        self.assertEqual(1, result)
        self.assertFalse(caller_conn.closed)


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

            def getsections_batch(self, redactionlayerid, document_pages, conn=None):
                received_connections.append(conn)
                return [{"documentid": 10, "pageno": 0, "section": "22"}]

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
