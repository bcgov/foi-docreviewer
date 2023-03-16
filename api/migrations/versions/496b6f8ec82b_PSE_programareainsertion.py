"""PSE programareainsertion

Revision ID: 496b6f8ec82b
Revises: 3d6b76fc4f9d
Create Date: 2022-12-30 10:31:32.974211

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '496b6f8ec82b'
down_revision = '3d6b76fc4f9d'
branch_labels = None
depends_on = None


def upgrade():    
    op.execute('''SELECT setval('"ProgramAreas_programareaid_seq"', (select max(programareaid) from public."ProgramAreas"), true);''')
    op.execute('INSERT INTO public."ProgramAreas"(name, type, isactive, bcgovcode, iaocode)	VALUES (\'Post-Secondary Education and Future Skills\', \'BC GOV Ministry\', True, \'PSE\', \'PSE\');commit;')


def downgrade():
    op.execute('DELETE FROM public."ProgramAreas" WHERE iaocode in (\'PSE\');commit;')
    op.execute('''SELECT setval('"ProgramAreas_programareaid_seq"', (select max(programareaid) from public."ProgramAreas"), true);''')
