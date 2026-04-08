from pathlib import Path


def test_docreviewer_record_mapping_query_escapes_like_wildcards():
    source = Path("services/dal/documenttemplate.py").read_text()

    assert "LIKE '%%' || dd.filepath || '%%'" in source
