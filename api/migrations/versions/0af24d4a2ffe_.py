"""New FOIPPA Sections (16.1 and Settlement Privilege)

Revision ID: 0af24d4a2ffe
Revises: 4d6e9f801234
Create Date: 2026-06-10 19:35:19.463524

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0af24d4a2ffe'
down_revision = '4d6e9f801234'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
               INSERT INTO public."Sections" (section, description, sortorder, isactive, createdby) VALUES ('', 'Settlement Privilege', 27, True, 'System');
               """)
    op.execute("""
               UPDATE public."Sections" SET sortorder = sortorder + 1 WHERE sortorder >= 6;
               """)
    op.execute("""
               INSERT INTO public."Sections" (section, description, sortorder, isactive, createdby) VALUES ('s.16.1', 'Judicial Comments', 6, True, 'System');
               """)


def downgrade():
    op.execute("""
               DELETE FROM public."Sections" WHERE description = 'Judicial Comments';
               """)
    op.execute("""
               UPDATE public."Sections" SET sortorder = sortorder - 1 WHERE sortorder >= 6;
               """)
    op.execute("""
               DELETE FROM public."Sections" WHERE description = 'Settlement Privilege';
               """)
