import pytest
from .conftest import record, prop


@pytest.mark.parametrize("stored", [None, 0])
def test_empty_count_uses_incoming(calculation, message, stored):
    calculation.stored = stored
    message.pagecount = 7
    assert calculation.calculate(message) == {"prevpagecount": stored, "calculatedpagecount": 7}
    assert calculation.updates == [("41", 7, "synthetic")]
    assert calculation.reads == []


@pytest.mark.parametrize("stored", [None, 0, 9, "0", "9"])
def test_missing_incoming_recomputes(calculation, message, stored):
    calculation.stored = stored
    calculation.records = [record(1), record(2, 1)]
    calculation.properties = [prop(1, 3), prop(2, 2)]
    assert calculation.calculate(message) == {"prevpagecount": stored, "calculatedpagecount": 5}
    assert calculation.updates == [("41", 5, "synthetic")]


@pytest.mark.parametrize("stored", [9, "0"])
def test_existing_count_ignores_incoming(calculation, message, stored):
    calculation.stored = stored
    message.pagecount = 777
    calculation.records = [record(1), record(2, 1)]
    calculation.properties = [prop(1, 3), prop(2, 2)]
    assert calculation.calculate(message)["calculatedpagecount"] == 5
    assert calculation.updates == [("41", 5, "synthetic")]


def test_equal_integer_count_avoids_update(calculation, message):
    calculation.stored = 0
    assert calculation.calculate(message)["calculatedpagecount"] == 0
    assert calculation.updates == []


@pytest.mark.parametrize("stored,updates", [(None, []), (0, [("41", None, "synthetic")])])
def test_explicit_null_incoming_is_selected(calculation, message, stored, updates):
    calculation.stored = stored
    message.pagecount = None
    assert calculation.calculate(message) == {"prevpagecount": stored, "calculatedpagecount": None}
    assert calculation.updates == updates


def test_nested_duplicate_and_excluded_records(calculation, message):
    calculation.records = [record(1), record(2, 1), record(3, 2), record(4, 1),
                           record(10), record(11, 10), record(20, isportfolio=True),
                           record(30, incompatible=True)]
    calculation.properties = [prop(1, 3, "parent"), prop(2, 2, "attachment"),
                              prop(3, 4), prop(4, 2, "attachment"),
                              prop(10, 3, "parent"), prop(11, 99),
                              prop(20, 99), prop(30, 99)]
    calculation.deleted = [99]
    assert calculation.calculate(message)["calculatedpagecount"] == 9
    assert calculation.updates == []
    assert calculation.reads == [("41", [99]), ("41", [99])]


@pytest.mark.parametrize("modified,size,expected", [("same", 100, 5), ("different", 100, 7),
                                                   ("same", 200, 7)])
def test_msg_attachments_match_filename_size_and_modified(calculation, message, modified, size, expected):
    a, b = record(2, 1, filesize=100, lastmodified="same"), record(3, 1, filesize=size, lastmodified=modified)
    for item in (a, b):
        item.update(filepath="synthetic/mail.msg", filename="mail.msg")
    calculation.records = [record(1), a, b]
    calculation.properties = [prop(1, 3), prop(2, 2), prop(3, 2)]
    for item in calculation.properties[1:]:
        item["filename"] = "mail.msg"
    assert calculation.calculate(message)["calculatedpagecount"] == expected


@pytest.mark.parametrize("records", [[], [record(1)]])
def test_missing_properties_count_zero(calculation, message, records):
    calculation.records = records
    assert calculation.calculate(message)["calculatedpagecount"] == 0
    assert calculation.updates == [("41", 0, "synthetic")]
