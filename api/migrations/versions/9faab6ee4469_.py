"""empty message

Revision ID: 9faab6ee4469
Revises: 828d870c000f
Create Date: 2025-06-25 10:42:02.557162

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9faab6ee4469'
down_revision = '828d870c000f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'BCGovIDIRs',
        sa.Column('sAMAccountName', sa.Text, primary_key=True, nullable=False),
        schema='public'
    )

def downgrade():
    op.drop_table('BCGovIDIRs', schema='public')
