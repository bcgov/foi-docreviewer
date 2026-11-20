"""FOIMOD-5515: Document Reviewer rows for EMP (replaces ECS), LHS (replaces HSG) and EDT (replaces JED).

Revision ID: 8f302508bcd4
Revises: d3de6e5bea18
Create Date: 2026-11-20

Companion of Flow's revision a0134b09838d (foi-flow, request-management-api). Same names and codes.

For each new ministry, this revision adds:
  * DocumentPathMapper: one active Records row for "<new>-<DEDUPE_S3_ENV>-e". Reviewer resolves a document's
    mapper by the exact bucket in its stored path, and the stitch and zip workers build the same name from
    bcgovcode. When the old ministry has a Records row ("<old>-<env>-e"), its attributes (storage credentials) are
    copied. Otherwise attributes are left empty and must be filled through the credential process, as for the
    rows created by revision 641ae620392d. Credentials are never printed.
  * ProgramAreas: one row, for catalogue consistency with Flow. Reviewer's API doesn't read this table (divisions
    come from Flow), so the old ministries are not deactivated or renamed here.

The upgrade refuses to run when DEDUPE_S3_ENV is missing, or when a new code or bucket already exists (Reviewer's
mapper lookup ignores isactive, so inactive rows count).

The downgrade removes only this revision's rows and refuses while any document is stored in a new bucket.
"""
import logging
import os
import re

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '8f302508bcd4'
down_revision = 'd3de6e5bea18'
branch_labels = None
depends_on = None

logger = logging.getLogger(f'alembic.{revision}')

CREATED_BY = 'FOIMOD-5515'
S3_ENVIRONMENT_ENV = 'DEDUPE_S3_ENV'
CATALOGUE_TYPE = 'BC GOV Ministry'

REPLACEMENTS = (
    {'old': 'ECS', 'new': 'EMP', 'name': 'Ministry of Energy, Mines and Petroleum Resources'},
    {'old': 'HSG', 'new': 'LHS', 'name': 'Ministry of Local Government, Housing, Sport and Culture'},
    {'old': 'JED', 'new': 'EDT', 'name': 'Ministry of Economic Development and Tourism'},
)


def _fail(message):
    raise RuntimeError(f'{revision}: {message}')


def _scalar(conn, sql, **params):
    return conn.execute(sa.text(sql), params).scalar()


def _environment():
    environment = os.getenv(S3_ENVIRONMENT_ENV)
    if not environment or not re.fullmatch(r'[a-z]+', environment):
        _fail(f'{S3_ENVIRONMENT_ENV} must be set (e.g. dev, test, prod)')
    return environment


def _bucket(code, environment):
    return f'{code.lower()}-{environment}-e'


def _add(conn, r, environment):
    old, new = r['old'], r['new']
    bucket = _bucket(new, environment)
    if _scalar(conn, 'SELECT count(*) FROM public."ProgramAreas" WHERE upper(bcgovcode) = :c OR upper(iaocode) = :c',
               c=new):
        _fail(f'a ministry with code {new} already exists')
    if _scalar(conn, 'SELECT count(*) FROM public."DocumentPathMapper" WHERE lower(bucket) = :b', b=bucket):
        _fail(f'a DocumentPathMapper row for bucket {bucket} already exists')

    conn.execute(sa.text('''
        INSERT INTO public."ProgramAreas" (name, type, bcgovcode, iaocode, isactive)
        VALUES (:name, :type, :code, :code, TRUE)'''),
        {'name': r['name'], 'type': CATALOGUE_TYPE, 'code': new},
    )
    old_id = _scalar(conn, '''SELECT documentpathid FROM public."DocumentPathMapper"
                             WHERE category = 'Records' AND lower(bucket) = :b ORDER BY isactive DESC, documentpathid
                             LIMIT 1''', b=_bucket(old, environment))
    conn.execute(sa.text('''
        INSERT INTO public."DocumentPathMapper" (category, bucket, attributes, isactive, createdby, created_at)
        VALUES ('Records', :bucket,
                (SELECT attributes FROM public."DocumentPathMapper" WHERE documentpathid = :id),
                TRUE, :createdby, now())'''),
        {'bucket': bucket, 'createdby': CREATED_BY, 'id': old_id},
    )
    if old_id is None:
        logger.warning('%s: no Records row for %s; %s has no credentials, fill them through the credential process',
                       revision, _bucket(old, environment), bucket)


def upgrade():
    conn = op.get_bind()
    environment = _environment()
    for replacement in REPLACEMENTS:
        _add(conn, replacement, environment)


def downgrade():
    conn = op.get_bind()
    for r in REPLACEMENTS:
        new = r['new']
        buckets = [row[0] for row in conn.execute(sa.text('''
            SELECT bucket FROM public."DocumentPathMapper"
             WHERE category = 'Records' AND createdby = :createdby AND bucket ILIKE lower(:code) || '-%' '''),
            {'createdby': CREATED_BY, 'code': new}).fetchall()]
        for bucket in buckets:
            # Stored paths look like https://<host>/<bucket>/<key>.
            if _scalar(conn, 'SELECT count(*) FROM public."DocumentMaster" WHERE filepath LIKE :p',
                       p=f'%://%/{bucket}/%'):
                _fail(f'documents are stored in {bucket}; the mapping cannot be removed')
        conn.execute(sa.text('''DELETE FROM public."DocumentPathMapper"
                                WHERE category = 'Records' AND createdby = :createdby AND bucket = ANY(:buckets)'''),
                     {'createdby': CREATED_BY, 'buckets': buckets})
        conn.execute(sa.text('DELETE FROM public."ProgramAreas" WHERE bcgovcode = :c AND iaocode = :c AND name = :n'),
                     {'c': new, 'n': r['name']})
