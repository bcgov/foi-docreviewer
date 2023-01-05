"""empty message

Revision ID: b9ecac992673
Revises: 92764562d406
Create Date: 2022-12-23 09:53:55.947451

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'b9ecac992673'
down_revision = '92764562d406'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('FileConversionJob',
        sa.Column('fileconversionjobid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('ministryrequestid', sa.Integer(), nullable=False),
        sa.Column('createdat', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('batch', sa.String(length=120), nullable=False), 
        sa.Column('trigger', sa.String(length=120), nullable=False), 
        sa.Column('inputfilepath', sa.String(length=240), nullable=False), 
        sa.Column('outputfilepath', sa.String(length=240), nullable=True), 
        sa.Column('filename', sa.String(length=500), nullable=False), 
        sa.Column('status', sa.String(length=120), nullable=False), 
        sa.Column('parentfilepath', sa.String(length=240), nullable=True), 
        sa.Column('parentfilename', sa.String(length=500), nullable=True), 
        sa.Column('message', sa.Text, nullable=True),
        sa.PrimaryKeyConstraint('fileconversionjobid', 'version')
    )

    op.create_table('DeduplicationJob',
        sa.Column('deduplicationjobid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('ministryrequestid', sa.Integer(), nullable=False),
        sa.Column('createdat', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('batch', sa.String(length=120), nullable=False), 
        sa.Column('trigger', sa.String(length=120), nullable=False), 
        sa.Column('type', sa.String(length=50), nullable=False), 
        sa.Column('filepath', sa.String(length=240), nullable=False), 
        sa.Column('filename', sa.String(length=500), nullable=False), 
        sa.Column('status', sa.String(length=120), nullable=False), 
        sa.Column('message', sa.Text, nullable=True),
        sa.PrimaryKeyConstraint('deduplicationjobid','version')
    )


def downgrade():
    op.drop_table('FileConversionJob')
    op.drop_table('DeduplicationJob')
