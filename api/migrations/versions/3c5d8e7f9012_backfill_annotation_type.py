"""backfill annotation type

Revision ID: 3c5d8e7f9012
Revises: 2b4c7d6e8f90
Create Date: 2026-05-13 11:37:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c5d8e7f9012'
down_revision = '2b4c7d6e8f90'
branch_labels = None
depends_on = None

BATCH_SIZE = 50000


def upgrade():
    bind = op.get_bind()

    with op.get_context().autocommit_block():
        while True:
            updated_count = bind.execute(
                sa.text(
                    """
                    WITH batch AS (
                        SELECT annotationid, version
                        FROM public."Annotations"
                        WHERE annotationtype IS NULL
                        ORDER BY annotationid, version
                        LIMIT :batch_size
                    ),
                    updated AS (
                        UPDATE public."Annotations" a
                        SET annotationtype = lower(
                            substring(
                                a.annotation FROM '^\\s*(?:<\\?xml[^>]*\\?>\\s*)?<([A-Za-z_][A-Za-z0-9_.:-]*)[\\s>/]'
                            )
                        )
                        FROM batch
                        WHERE a.annotationid = batch.annotationid
                          AND a.version = batch.version
                        RETURNING 1
                    )
                    SELECT count(*) FROM updated;
                    """
                ),
                {"batch_size": BATCH_SIZE},
            ).scalar()

            if updated_count == 0:
                break


def downgrade():
    pass
