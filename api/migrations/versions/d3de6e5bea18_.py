"""Add Short Codes column to Sections Table

Revision ID: d3de6e5bea18
Revises: f5199c0ffee1
Create Date: 2026-09-16 22:17:04.667572

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd3de6e5bea18'
down_revision = 'f5199c0ffee1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("Sections", sa.Column("shortcode", sa.String(length=50), nullable=True))

    # Add shortcodes to coresponding sections
    op.execute('''UPDATE public."Sections" SET shortcode = 'F3' WHERE section = 's. 3';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F12' WHERE section = 's. 12';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F13' WHERE section = 's. 13';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F14' WHERE section = 's. 14';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F15' WHERE section = 's. 15';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F16' WHERE section = 's. 16';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F16.1' WHERE section = 's. 16.1';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F17' WHERE section = 's. 17';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F18' WHERE section = 's. 18';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F18.1' WHERE section = 's. 18.1';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F19' WHERE section = 's. 19';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F20' WHERE section = 's. 20';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F21' WHERE section = 's. 21';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F22' WHERE section = 's. 22';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'F22.1' WHERE section = 's. 22.1';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'C4' WHERE section = 's. 3 - CFCSA s. 24';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'A73' WHERE section = 's. 3 - AA s. 73';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'G46' WHERE section = 's. 3 - AGA s. 46';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'CA63' WHERE section = 's. 3 - CA s. 63';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'CA64' WHERE section = 's. 3 - CA s. 64';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'FM43' WHERE section = 's. 3 - FMEA s. 43';''')
    op.execute('''UPDATE public."Sections" SET shortcode = 'PA' WHERE section = 's. 3 - PA';''')

    # op.execute('''
    # INSERT INTO public."Sections" (section, description, sortorder, isactive, createdby, shortcode) 
    # VALUES ('s. 8', 'Refuse to confirm or deny', 29, True, 'System', 'F8');
    # ''')
    op.execute('''
    INSERT INTO public."Sections" (section, description, sortorder, isactive, createdby, shortcode) 
    VALUES ('s. 3 - s. 22 - CFCSA s. 77(1)', 'Disclosure harmful to personal privacy, identity of a Reporter under CFCSA', 30, True, 'System', 'C1');
    ''')
    op.execute('''
    INSERT INTO public."Sections" (section, description, sortorder, isactive, createdby, shortcode) 
    VALUES ('s. 3 - s. 22 - CFCSA s. 77(2)(b)', 'Disclosure harmful to personal privacy, information collected in confidence under CFCSA Investigation', 31, True, 'System', 'C2');
    ''')
    op.execute('''
    INSERT INTO public."Sections" (section, description, sortorder, isactive, createdby, shortcode) 
    VALUES ('s. 3 - s. 22 - CFCSA s. 77(2)(a)', 'Disclosure harmful to personal privacy, jeopardize an investigation under CFCSA', 32, True, 'System', 'C7');
    ''')


def downgrade():
    op.drop_column("Sections", "shortcode")
    # op.execute('''
    # DELETE FROM public."Sections" WHERE section = 's. 8';
    # ''')
    op.execute('''
    DELETE FROM public."Sections" WHERE section = 's. 3 - s. 22 - CFCSA s. 77(1)';
    ''')
    op.execute('''
    DELETE FROM public."Sections" WHERE section = 's. 3 - s. 22 - CFCSA s. 77(2)(b)';
    ''')
    op.execute('''
    DELETE FROM public."Sections" WHERE section = 's. 3 - s. 22 - CFCSA s. 77(2)(a)';
    ''')