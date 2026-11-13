from sqlalchemy import text


def test_commit_rollback_and_savepoint_isolation(session):
    session.execute(
        text(
            "CREATE TEMP TABLE upgrade_transactions (id integer PRIMARY KEY) ON COMMIT DROP"
        )
    )
    session.execute(text("INSERT INTO upgrade_transactions VALUES (1)"))
    savepoint = session.begin_nested()
    session.execute(text("INSERT INTO upgrade_transactions VALUES (2)"))
    savepoint.rollback()
    assert [
        row[0] for row in session.execute(text("SELECT id FROM upgrade_transactions"))
    ] == [1]


def test_session_cleanup_after_query_failure(session):
    # Failing SQL must not poison later requests after rollback.
    import pytest
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        session.execute(text("SELECT * FROM no_such_upgrade_table"))
    session.rollback()
    assert session.execute(text("SELECT 1")).scalar() == 1
