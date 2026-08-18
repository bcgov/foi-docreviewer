import importlib.util
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[3]
MIGRATION_PATH = (
    REPOSITORY_ROOT
    / "api/migrations/versions/f5199c0ffee1_compressionjob_workload.py"
)


class RecordingOperations:
    def __init__(self):
        self.calls = []

    def add_column(self, *args, **kwargs):
        self.calls.append(("add_column", args, kwargs))

    def create_check_constraint(self, *args, **kwargs):
        self.calls.append(("create_check_constraint", args, kwargs))

    def drop_constraint(self, *args, **kwargs):
        self.calls.append(("drop_constraint", args, kwargs))

    def drop_column(self, *args, **kwargs):
        self.calls.append(("drop_column", args, kwargs))


def load_migration_module():
    specification = importlib.util.spec_from_file_location(
        "compressionjob_workload_migration", MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_compressionjob_workload_migration_orders_schema_changes():
    assert MIGRATION_PATH.exists(), "workload migration must be added"

    migration = load_migration_module()
    operations = RecordingOperations()
    migration.op = operations

    migration.upgrade()

    assert migration.revision == "f5199c0ffee1"
    assert migration.down_revision == "0af24d4a2ffe"
    assert [call[0] for call in operations.calls] == [
        "add_column",
        "create_check_constraint",
    ]
    assert operations.calls[0][1][0] == "CompressionJob"
    assert operations.calls[0][1][1].name == "workload"
    assert operations.calls[0][1][1].nullable is True
    assert operations.calls[1][1] == (
        "ck_compressionjob_workload",
        "CompressionJob",
        "workload IS NULL OR workload IN ('normal', 'large')",
    )

    operations.calls.clear()
    migration.downgrade()

    assert [call[0] for call in operations.calls] == ["drop_constraint", "drop_column"]
    assert operations.calls[0][1] == (
        "ck_compressionjob_workload",
        "CompressionJob",
    )
    assert operations.calls[0][2] == {"type_": "check"}
    assert operations.calls[1][1] == ("CompressionJob", "workload")
