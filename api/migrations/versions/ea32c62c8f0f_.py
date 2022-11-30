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
    op.execute('UPDATE public."Documents" SET filename = \'1001 Books.pdf\', filepath = \'test/1001 Books.pdf\', pagecount = 2272 WHERE documentid = 1')
    op.execute('UPDATE public."Documents" SET filename = \'6 Important factors.pdf\', filepath = \'test/6 Important factors.pdf\', pagecount = 9 WHERE documentid = 2')
    op.execute('UPDATE public."Documents" SET filename = \'Unix and Linux System.pdf\', filepath = \'test/Unix and Linux System.pdf\', pagecount = 1885 WHERE documentid = 3')
    op.execute('UPDATE public."Documents" SET filename = \'6 Important factors.pdf\', filepath = \'test/6 Important factors.pdf\', pagecount = 9 WHERE documentid = 4')
    op.execute('UPDATE public."Documents" SET filename = \'1001 Books.pdf\', filepath = \'test/1001 Books.pdf\', pagecount = 2272 WHERE documentid = 5')
    op.execute('UPDATE public."Documents" SET filename = \'6 Important factors.pdf\', filepath = \'test/6 Important factors.pdf\', pagecount = 9 WHERE documentid = 6')


def downgrade():
    op.alter_column('Documents', 'filepath',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
    op.execute('UPDATE public."Documents" SET filename = \'sample1.pdf\', filepath = \'/files/sample1.pdf\', pagecount = 9 WHERE documentid = 1')
    op.execute('UPDATE public."Documents" SET filename = \'sample2.pdf\', filepath = \'/files/sample2.pdf\', pagecount = 2 WHERE documentid = 2')
    op.execute('UPDATE public."Documents" SET filename = \'sample1.pdf\', filepath = \'/files/sample1.pdf\', pagecount = 9 WHERE documentid = 3')
    op.execute('UPDATE public."Documents" SET filename = \'sample1.pdf\', filepath = \'/files/sample1.pdf\', pagecount = 9 WHERE documentid = 4')
    op.execute('UPDATE public."Documents" SET filename = \'sample1.pdf\', filepath = \'/files/sample1.pdf\', pagecount = 9 WHERE documentid = 5')
    op.execute('UPDATE public."Documents" SET filename = \'sample2.pdf\', filepath = \'/files/sample2.pdf\', pagecount = 2 WHERE documentid = 6')
