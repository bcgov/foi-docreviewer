"""Add workload classification to compression jobs.

Revision ID: f5199c0ffee1
Revises: 0af24d4a2ffe
Create Date: 2026-08-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f5199c0ffee1"
down_revision = "0af24d4a2ffe"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "CompressionJob",
        sa.Column("workload", sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        "ck_compressionjob_workload",
        "CompressionJob",
        "workload IS NULL OR workload IN ('normal', 'large')",
    )


def downgrade():
    op.drop_constraint(
        "ck_compressionjob_workload", "CompressionJob", type_="check"
    )
    op.drop_column("CompressionJob", "workload")
