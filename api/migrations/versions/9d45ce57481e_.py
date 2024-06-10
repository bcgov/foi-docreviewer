"""empty message

Revision ID: 9d45ce57481e
Revises: 18a45d1b33cc
Create Date: 2024-06-06 10:19:45.739225

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9d45ce57481e'
down_revision = '18a45d1b33cc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('PDFStitchJobAttributes',
        sa.Column('attributesid', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pdfstitchjobid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('ministryrequestid', sa.Integer(), nullable=False),        
        sa.Column('attributes', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('createdat', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('createdby', sa.String(length=120), nullable=True), 
        sa.PrimaryKeyConstraint('attributesid'),
        sa.ForeignKeyConstraint(['pdfstitchjobid', 'version'], ['PDFStitchJob.pdfstitchjobid', 'PDFStitchJob.version'], )
    )


def downgrade():
    op.drop_table('PDFStitchJobAttributes')

