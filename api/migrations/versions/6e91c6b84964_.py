"""empty message

Revision ID: 6e91c6b84964
Revises: 18a45d1b33cc
Create Date: 2024-10-18 11:25:57.222327

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6e91c6b84964'
down_revision = '18a45d1b33cc'
branch_labels = None
depends_on = None


def upgrade():

    op.execute('INSERT INTO public."RedactionLayers"(name, description, sortorder, isactive, createdby, created_at) VALUES (\'Open Info\', \'Open Info\', 4, True, \'System\', now());commit;') 

def downgrade():

    op.execute('delete from public."RedactionLayers" WHERE name in (\'Open Info\');commit;')
    # ### end Alembic commands ###
