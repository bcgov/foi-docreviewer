import importlib.util
import json
import sys
import types
from pathlib import Path


REDACTION_SUMMARY_PATH = Path(__file__).resolve().parents[1] / "services" / "dts" / "redactionsummary.py"


def load_redactionsummary_module(module_name, fake_documentpageflag):
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
