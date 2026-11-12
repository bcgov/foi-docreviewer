import importlib
import pytest


@pytest.mark.parametrize("failure,payload", [(None, {"prevpagecount": 9, "calculatedpagecount": 0}),
                                           ("metadata", None), ("update", None)])
def test_job_history_including_swallowed_failures(monkeypatch, calculation, message, failure, payload):
    module = importlib.import_module("services.pagecountservice.pagecountcalculationservice")
    events = []

    class Jobs:
        def pagecalculatorjobstart(self, msg):
            events.append(("started", msg.jobid))

        def pagecalculatorjobend(self, msg, error, pagecount="", message=""):
            events.append(("error" if error else "completed", pagecount, message))

    calculation.failure = failure
    monkeypatch.setattr(module, "documentservice", Jobs)
    module.pagecountcalculationservice().processmessage(message)
    assert events == [("started", 73), ("completed", payload, "")]


def test_start_failure_records_error(monkeypatch, message):
    module = importlib.import_module("services.pagecountservice.pagecountcalculationservice")
    events = []

    class Jobs:
        def pagecalculatorjobstart(self, msg):
            raise RuntimeError("synthetic start failure")

        def pagecalculatorjobend(self, msg, error, **kwargs):
            events.append((msg.jobid, error, kwargs))

    monkeypatch.setattr(module, "documentservice", Jobs)
    module.pagecountcalculationservice().processmessage(message)
    assert events == [(73, True, {"pagecount": "", "message": "synthetic start failure"})]
