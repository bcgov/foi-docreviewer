"""empty message

Revision ID: b9a82a00b13a
Revises: ffaeedd62e37
Create Date: 2023-08-16 19:54:00.683784

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b9a82a00b13a'
down_revision = 'ffaeedd62e37'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('DocumentPageflags', sa.Column('redactionlayerid', sa.Integer, nullable=False, server_default='1'))
    op.create_table('DocumentPageflagHistory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('documentpageflagid', sa.Integer(), nullable=False),
        sa.Column('foiministryrequestid', sa.Integer(), nullable=False),
        sa.Column('documentid', sa.Integer(), nullable=False),
        sa.Column('documentversion', sa.Integer(), nullable=False),
        sa.Column('pageflag',  postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('attributes',  postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('createdby', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updatedby',  postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('redactionlayerid',  sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['documentpageflagid'], ['DocumentPageflags.id'])
    )


def downgrade():
    op.drop_column('DocumentPageflags', 'redactionlayerid')
    op.drop_table('DocumentPageflagHistory', 'redactionlayerid')
