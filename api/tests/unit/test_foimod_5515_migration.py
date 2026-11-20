"""FOIMOD-5515 Reviewer migration and ministry groups (no database)."""

import importlib.util
from pathlib import Path

import pytest

API_ROOT = Path(__file__).parents[2]


def _load(name, relative_path):
    # Loaded by path: importing the reviewer_api package needs the full app configuration.
    spec = importlib.util.spec_from_file_location(name, API_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = _load("foimod_5515_migration", "migrations/versions/8f302508bcd4_FOIMOD_5515_new_ministries.py")
MinistryTeamWithKeycloackGroup = _load("reviewer_enums", "reviewer_api/utils/enums.py").MinistryTeamWithKeycloackGroup


def test_replacements_match_flow():
    assert [(r["old"], r["new"]) for r in migration.REPLACEMENTS] == [("ECS", "EMP"), ("HSG", "LHS"), ("JED", "EDT")]


def test_follows_the_current_head():
    assert migration.down_revision == "d3de6e5bea18"


@pytest.mark.parametrize("code,environment,expected", [
    ("EMP", "dev", "emp-dev-e"),
    ("LHS", "prod", "lhs-prod-e"),
    ("EDT", "test", "edt-test-e"),
])
def test_bucket_name(code, environment, expected):
    assert migration._bucket(code, environment) == expected


@pytest.mark.parametrize("value", [None, "", "DEV", "dev-1"])
def test_environment_is_required(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("DEDUPE_S3_ENV", raising=False)
    else:
        monkeypatch.setenv("DEDUPE_S3_ENV", value)
    with pytest.raises(RuntimeError):
        migration._environment()


@pytest.mark.parametrize("code", ["EMP", "LHS", "EDT", "ECS", "HSG", "JED"])
def test_ministry_groups(code):
    assert MinistryTeamWithKeycloackGroup[code].value == f"{code} Ministry Team"
