"""Add new section (NOT RESPONSIVE)

Revision ID: e0e3a10b850d
Revises: 549893ea9059
Create Date: 2024-01-29 13:01:30.668629

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e0e3a10b850d'
down_revision = '549893ea9059'
branch_labels = None
depends_on = None


def upgrade():
    #Adjust all sort orders after new section by adding +1 
    op.execute('UPDATE public."Sections" SET sortorder = sortorder + 1 WHERE sortorder > 14;commit;')
    #Add new section and make its sort order 15
    op.execute('INSERT INTO public."Sections" (section, description, sortorder, isactive, createdby) VALUES (\'NR\', \'Not Responsive\', 15, True, \'System\');commit;')

def downgrade():
    op.execute('DELETE FROM public."Sections" WHERE section in (\'NR\');commit;')
    op.execute('UPDATE public."Sections" SET sortorder = sortorder - 1 WHERE sortorder > 14;commit;')