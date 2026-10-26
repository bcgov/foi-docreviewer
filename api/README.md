# FOI Document Reviewer API

The API serves document, annotation, redaction-layer and page-flag operations.

Python 3.13 upgrade verification and DEV acceptance steps are documented in
[python-upgrade-validation.md](docs/python-upgrade-validation.md). Run tests with
the isolated Docker runner described there; fixtures reject shared endpoints.

Operational migration commands remain:

```bash
python manage.py db upgrade
python manage.py db current
python manage.py db heads
python manage.py list_routes
```

The entrypoint runs migrations before starting the server. An upgrade does not
require a new migration revision. Full-suite legacy failures are listed in the
[test comparison](docs/python-upgrade-test-comparison.md).
