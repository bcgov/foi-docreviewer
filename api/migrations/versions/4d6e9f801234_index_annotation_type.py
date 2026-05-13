"""index annotation type

Revision ID: 4d6e9f801234
Revises: 3c5d8e7f9012
Create Date: 2026-05-13 11:38:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '4d6e9f801234'
down_revision = '3c5d8e7f9012'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
            'idx_annotations_active_type_layer_doc_page '
            'ON public."Annotations" '
            '(annotationtype, redactionlayerid, documentid, documentversion, pagenumber) '
            'WHERE isactive = TRUE'
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            'DROP INDEX CONCURRENTLY IF EXISTS '
            'public.idx_annotations_active_type_layer_doc_page'
        )
