"""empty message

Revision ID: 13766f2831b6
Revises: 36e7b771fbb5
Create Date: 2023-10-03 13:53:19.344756

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "13766f2831b6"
down_revision = "36e7b771fbb5"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        'ALTER TABLE public."Annotations" DROP CONSTRAINT "annotation_version_key";'
    )
    op.execute(
        'ALTER TABLE public."Annotations" ADD CONSTRAINT annotation_version_redactionlayerid_key UNIQUE (annotationname, version, redactionlayerid);'
    )


def downgrade():
    op.execute(
        'ALTER TABLE public."Annotations" DROP CONSTRAINT "annotation_version_redactionlayerid_key";'
    )
