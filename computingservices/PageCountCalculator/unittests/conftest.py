"""Offline tests use real imports and replace only database collaborators."""
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("REDIS_PORT", "6379")


@pytest.fixture
def calculation(monkeypatch):
    module = importlib.import_module("services.pagecountservice.pagecountservice")
    state = SimpleNamespace(stored=9, records=[], properties=[], deleted=[],
                            updates=[], reads=[], failure=None)

    class Ministry:
        def getlatestrecordspagecount(self, request):
            assert request == "41"
            return state.stored

        def updaterecordspagecount(self, request, count, user):
            if state.failure == "update":
                raise RuntimeError("synthetic update failure")
            state.updates.append((request, count, user))

    class Documents:
        def getdeleteddocuments(self, request):
            if state.failure == "metadata":
                raise RuntimeError("synthetic metadata failure")
            return state.deleted

        def getdedupestatus(self, request):
            return []

        def getdocumentmaster(self, request, deleted):
            state.reads.append((request, deleted))
            return deepcopy(state.records)

        def getdocumentproperties(self, request, deleted):
            state.reads.append((request, deleted))
            return deepcopy(state.properties)

    monkeypatch.setattr(module, "ministryervice", Ministry)
    monkeypatch.setattr(module, "documentservice", Documents)
    state.calculate = module.pagecountservice().calculatepagecount
    return state


@pytest.fixture
def message():
    return SimpleNamespace(jobid=73, ministryrequestid="41", createdby="synthetic")


def record(identifier, parent=None, **attributes):
    return dict(documentmasterid=identifier, recordid=identifier if parent is None else None,
                parentid=parent, filepath=f"synthetic/{identifier}.pdf", created_at=None,
                attributes={"incompatible": False, **attributes}, filename=f"{identifier}.pdf")


def prop(identifier, pages, hash_=None, **extra):
    return dict(documentmasterid=identifier, processingparentid=identifier,
                pagecount=pages, rank1hash=hash_ or str(identifier),
                filename=f"{identifier}.pdf", **extra)
