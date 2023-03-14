"""HSG Program Areas

Revision ID: ef2787700a08
Revises: 6ae623b1d72d
Create Date: 2023-02-13 13:08:49.059340

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef2787700a08'
down_revision = '6ae623b1d72d'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('INSERT INTO public."ProgramAreas"(name, type, isactive, bcgovcode, iaocode)	VALUES (\'Ministry of Housing\', \'BC GOV Ministry\', True, \'HSG\', \'HSG\');commit;')


def downgrade():
    op.execute('DELETE FROM public."ProgramAreas" WHERE iaocode in (\'HSG\');commit;')
