"""JED Program Areas

Revision ID: 0f31e19d3672
Revises: a9bc29e088d2
Create Date: 2023-01-05 16:06:41.673762

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0f31e19d3672'
down_revision = 'a9bc29e088d2'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('INSERT INTO public."ProgramAreas"(name, type, isactive, bcgovcode, iaocode)	VALUES (\'Jobs, Economic Development and Innovation\', \'BC GOV Ministry\', True, \'JED\', \'JED\');commit;')


def downgrade():
    op.execute('DELETE FROM public."ProgramAreas" WHERE iaocode in (\'JED\');commit;')
