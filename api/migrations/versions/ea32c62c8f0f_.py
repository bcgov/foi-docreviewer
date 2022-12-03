"""empty message

Revision ID: ea32c62c8f0f
Revises: b96f3a390985
Create Date: 2022-11-21 13:46:08.934385

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ea32c62c8f0f'
down_revision = 'cb81f7d5bfca'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('Documents', 'filepath',
               existing_type=sa.String(length=255),
               type_=sa.String(length=500),
               existing_nullable=False)
    op.execute('Truncate table public."Documents" RESTART IDENTITY CASCADE;commit;')
    op.execute('Truncate table public."DocumentTags" RESTART IDENTITY CASCADE;commit;')

    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'1001 Books.pdf\', \'test/1001 Books.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 2272);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'6 Important factors.pdf\', \'test/6 Important factors.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 9);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Unix and Linux System.pdf\', \'test/Unix and Linux System.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 1885);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'6 Important factors.pdf\', \'test/6 Important factors.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 9);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'1001 Books.pdf\', \'test/1001 Books.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 2272);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'6 Important factors.pdf\', \'test/6 Important factors.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 9);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'QA Review Form.pdf\', \'test/QA Review Form.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 4);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Request Summary - CORR Police Services.pdf\', \'test/Request Summary - CORR Police Services.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 2);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Request Summary - DVR Request - Corrections and Court Services.pdf\', \'test/Request Summary - DVR Request - Corrections and Court Services.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 3);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Sign Form - Calendars.pdf\', \'test/Sign Form - Calendars.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 2);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Sign Form - Expense.pdf\', \'test/Sign Form - Expense.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 2);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Sign Form.pdf\', \'test/Sign Form.pdf\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 3);commit;')
 
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (1, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (2, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (3, 1, \'{"divisions":[{"divisionid"\:2}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (4, 1, \'{"divisions":[{"divisionid"\:3}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (5, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (6, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (7, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (8, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (9, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (10, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (11, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (12, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')


def downgrade():
    op.alter_column('Documents', 'filepath',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)

    op.execute('Truncate table public."Documents" RESTART IDENTITY CASCADE;commit;')
    op.execute('Truncate table public."DocumentTags" RESTART IDENTITY CASCADE;commit;')