"""empty message

Revision ID: 92e790437c06
Revises: 118f76cb5ead
Create Date: 2023-03-21 16:21:45.149257

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '92e790437c06'
down_revision = '118f76cb5ead'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('PDFStitchJob',
        sa.Column('pdfstitchjobid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('ministryrequestid', sa.Integer(), nullable=False),        
        sa.Column('category', sa.String(length=50), nullable=False), 
        sa.Column('inputfiles', postgresql.JSON(astext_type=sa.Text()), nullable=False), 
        sa.Column('outputfiles', postgresql.JSON(astext_type=sa.Text()), nullable=True), 
        sa.Column('status', sa.String(length=120), nullable=False), 
        sa.Column('message', sa.Text, nullable=True),
        sa.Column('createdat', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('createdby', sa.String(length=120), nullable=True), 
        sa.PrimaryKeyConstraint('pdfstitchjobid', 'version')
    )

    op.create_table('PDFStitchPackage',
        sa.Column('pdfstitchpackageid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('ministryrequestid', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('finalpackagepath', sa.String(length=500), nullable=False), 
        sa.Column('createdat', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('createdby', sa.String(length=120), nullable=True), 
        sa.PrimaryKeyConstraint('pdfstitchpackageid')
    )


def downgrade():
    op.drop_table('PDFStitchJob')
    op.drop_table('PDFStitchPackage')

