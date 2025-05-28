"""empty message

Revision ID: 00e2b5eb7f75
Revises: 5ace86cdb21d
Create Date: 2025-05-27 15:08:00.864101

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00e2b5eb7f75'
down_revision = '5ace86cdb21d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'redline_content',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ministryrequestid', sa.Integer, nullable=False),
        sa.Column('redlineid', sa.String(36), nullable=False),
        sa.Column('documentid', sa.Integer, nullable=False),
        sa.Column('type', sa.String(250), nullable=False),
        sa.Column('section', sa.String(100), nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('category', sa.String(250), nullable=True),
        sa.Column('createdat', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('createdby', sa.String(250), nullable=True),
    )

def downgrade():
    op.drop_table('redline_content')