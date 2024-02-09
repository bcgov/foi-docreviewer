"""empty message

Revision ID: c787e6d82903
Revises: 549893ea9059
Create Date: 2024-02-06 15:12:03.310271

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c787e6d82903'
down_revision = '549893ea9059'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('PageCalculatorJob',
        sa.Column('pagecalculatorjobid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('ministryrequestid', sa.Integer(), nullable=False),
        sa.Column('inputmessage', postgresql.JSON(astext_type=sa.Text()), nullable=False), 
        sa.Column('pagecount', postgresql.JSON(astext_type=sa.Text()), nullable=True), 
        sa.Column('status', sa.String(length=120), nullable=False), 
        sa.Column('message', sa.Text, nullable=True),
        sa.Column('createdat', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('createdby', sa.String(length=120), nullable=True), 
        sa.PrimaryKeyConstraint('pagecalculatorjobid', 'version')
    )


def downgrade():
    op.drop_table('PageCalculatorJob')
