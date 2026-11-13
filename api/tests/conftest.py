"""Disposable peer fixtures; bootstrap validates before importing this file."""

import os
import sys

sys.path.insert(0, "/verification-scripts")
from check_test_environment import validate_test_environment

validate_test_environment(os.environ)
import pytest
import requests
from flask_migrate import Migrate, upgrade
from reviewer_api import create_app, setup_jwt_manager
from reviewer_api.auth import jwt as reviewer_jwt
from reviewer_api.models import db as _db


@pytest.fixture(scope="session")
def app(identity):
    application = create_app("testing")
    identity.configure(application)
    setup_jwt_manager(application, reviewer_jwt)
    with application.app_context():
        Migrate(application, _db)
    return application


@pytest.fixture
def app_request(app):
    return app


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def client_ctx(app):
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="session")
def db(app):
    with app.app_context():
        upgrade(directory="/verification-source/migrations")
    return _db


@pytest.fixture
def session(app, db):
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        from sqlalchemy.orm import scoped_session, sessionmaker
        import sqlalchemy

        if sqlalchemy.__version__.startswith("1."):
            sess = db.create_scoped_session(dict(bind=connection, binds={}))
        else:
            sess = scoped_session(
                sessionmaker(
                    bind=connection,
                    query_cls=db.Query,
                    join_transaction_mode="create_savepoint",
                )
            )
        previous = db.session
        db.session = sess
        try:
            yield sess
        finally:
            sess.remove()
            db.session = previous
            if transaction.is_active:
                transaction.rollback()
            connection.close()


@pytest.fixture(autouse=True)
def block_external_http(monkeypatch):
    original = requests.sessions.Session.request

    def guarded(self, method, url, *args, **kwargs):
        from urllib.parse import urlsplit

        if urlsplit(url).hostname not in {"storage", "fixtures"}:
            raise RuntimeError(
                "Unregistered HTTP request in isolated test: " + str(url)
            )
        kwargs.setdefault("timeout", 5)
        return original(self, method, url, *args, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", guarded)


@pytest.fixture(scope="session")
def identity():
    from tests.identity import SyntheticIdentity

    return SyntheticIdentity()
