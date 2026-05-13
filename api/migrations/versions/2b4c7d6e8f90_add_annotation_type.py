"""add annotation type

Revision ID: 2b4c7d6e8f90
Revises: 81eb14daaace
Create Date: 2026-05-13 11:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2b4c7d6e8f90'
down_revision = '81eb14daaace'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "Annotations",
        sa.Column("annotationtype", sa.String(length=40), nullable=True),
    )


def downgrade():
    op.drop_column("Annotations", "annotationtype")
