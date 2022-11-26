"""empty message

Revision ID: d0d4913c0299
Revises: ea32c62c8f0f
Create Date: 2022-11-25 18:19:47.036478

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0d4913c0299'
down_revision = 'ea32c62c8f0f'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'QA Review Form.docx\', \'test/QA Review Form.docx\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 4);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Request Summary - CORR Police Services.docx\', \'test/Request Summary - CORR Police Services.docx\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 2);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Request Summary - DVR Request - Corrections and Court Services.docx\', \'test/Request Summary - DVR Request - Corrections and Court Services.docx\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 3);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Sign Form - Calendars.docx\', \'test/Sign Form - Calendars.docx\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 3);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Sign Form - Expense.docx\', \'test/Sign Form - Expense.docx\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 2);commit;')
    op.execute('INSERT INTO public."Documents" (version, filename, filepath, attributes, foiministryrequestid, createdby, created_at, updated_at, statusid, pagecount) VALUES (1, \'Sign Form.docx\', \'test/Sign Form.docx\', \'{}\', 1, \'{}\', now()::Date, now()::Date, 1, 3);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (7, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (8, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (9, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (10, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (11, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')
    op.execute('INSERT INTO public."DocumentTags" (documentid, documentversion, tag, createdby, created_at) VALUES (12, 1, \'{"divisions":[{"divisionid"\:1}]}\', \'{}\', now()::Date);commit;')


def downgrade():
    op.execute('DELETE from public."Documents" where documentid in (7, 8, 9, 10, 11, 12)')
    op.execute('DELETE from public."DocumentTags" where documentid in (7, 8, 9, 10, 11, 12)')
