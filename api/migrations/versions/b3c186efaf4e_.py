"""empty message

Revision ID: b3c186efaf4e
Revises: 13766f2831b6
Create Date: 2023-10-12 14:32:45.457720

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3c186efaf4e"
down_revision = "13766f2831b6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        'CREATE INDEX "idx_annotations_multicolumn" ON "Annotations" (annotationname, redactionlayerid, documentid, pagenumber);'
    )


def downgrade():
    op.execute('DROP INDEX "idx_annotations_multicolumn";')
