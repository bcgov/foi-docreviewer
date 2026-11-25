"""Rename BC Corrections ProgramArea

Revision ID: 2a950b212ff2
Revises: 8f302508bcd4
Create Date: 2026-11-25 22:12:16.423760

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import logging


# revision identifiers, used by Alembic.
revision = '2a950b212ff2'
down_revision = '8f302508bcd4'
branch_labels = None
depends_on = None

logger = logging.getLogger(f'alembic.{revision}')

RENAMES = {
    'COR': ('Corrections Branch', 'BC Corrections'),
}

def _fail(message):
    raise RuntimeError(f'{revision}: {message}')


def _scalar(conn, sql, **params):
    return conn.execute(sa.text(sql), params).scalar()

def _rename(conn):
    for code, (old_name, new_name) in RENAMES.items():
        current = _scalar(conn, 'SELECT name FROM public."ProgramAreas" WHERE bcgovcode = :c', c=code)
        if current is None:
            _fail(f'ministry {code} does not exist')
        if current != old_name:
            _fail(f'ministry {code} is named {current!r}, expected {old_name!r}')
    for code, (old_name, new_name) in RENAMES.items():
        conn.execute(sa.text('UPDATE public."ProgramAreas" SET name = :n WHERE bcgovcode = :c'), {'n': new_name, 'c': code})
        logger.info(f'Renamed ministry {code} from {old_name!r} to {new_name!r}')


def upgrade():
    conn = op.get_bind()
    _rename(conn)


def downgrade():
    conn = op.get_bind()
    for code, (old_name, new_name) in RENAMES.items():
        conn.execute(sa.text('UPDATE public."ProgramAreas" SET name = :old WHERE bcgovcode = :c AND name = :new'),
                {'old': old_name, 'new': new_name, 'c': code})