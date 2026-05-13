"""backfill annotation type

Revision ID: 3c5d8e7f9012
Revises: 2b4c7d6e8f90
Create Date: 2026-05-13 11:37:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '3c5d8e7f9012'
down_revision = '2b4c7d6e8f90'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE public."Annotations"
        SET annotationtype = lower(
            substring(
                annotation FROM '^\\s*(?:<\\?xml[^>]*\\?>\\s*)?<([A-Za-z_][A-Za-z0-9_.:-]*)[\\s>/]'
            )
        )
        WHERE annotationtype IS NULL;
        """
    )


def downgrade():
    op.execute('UPDATE public."Annotations" SET annotationtype = NULL;')
