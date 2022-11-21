"""empty message

Revision ID: ea32c62c8f0f
Revises: b96f3a390985
Create Date: 2022-11-21 13:46:08.934385

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ea32c62c8f0f'
down_revision = 'b96f3a390985'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('Documents', 'filepath',
               existing_type=sa.String(length=255),
               type_=sa.String(length=500),
               existing_nullable=False)
    op.execute('UPDATE public."Documents" SET filename = \'1001 Books.pdf\', filepath = \'https://citz-foi-prod.objectstore.gov.bc.ca/dev-forms-foirequests/test/1001%20Books.pdf?response-content-type=application%2Fpdf&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA95AE3AF038A4DC93%2F20221121%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20221121T201604Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=159bcd2e7ad47fc3a2f0bc49ba45306c98ff048778d69fc1d3e24ace7d008528\' WHERE documentid = 1')
    op.execute('UPDATE public."Documents" SET filename = \'6 Important factors.pdf\', filepath = \'https://citz-foi-prod.objectstore.gov.bc.ca/dev-forms-foirequests/test/6%20Important%20factors.pdf?response-content-type=application%2Fpdf&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA95AE3AF038A4DC93%2F20221121%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20221121T201706Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=4a3708594b0413187101d53f13ff98873f06862a9ccac647820231c2796a8721\' WHERE documentid = 2')
    op.execute('UPDATE public."Documents" SET filename = \'Unix and Linux System.pdf\', filepath = \'https://citz-foi-prod.objectstore.gov.bc.ca/dev-forms-foirequests/test/Unix%20and%20Linux%20System.pdf?response-content-type=application%2Fpdf&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA95AE3AF038A4DC93%2F20221121%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20221121T201444Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=e7c239c267d6f108c9e043a32a647e6094adbb214559e79bacda762f23ed530f\' WHERE documentid = 3')
    op.execute('UPDATE public."Documents" SET filename = \'6 Important factors.pdf\', filepath = \'https://citz-foi-prod.objectstore.gov.bc.ca/dev-forms-foirequests/test/6%20Important%20factors.pdf?response-content-type=application%2Fpdf&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA95AE3AF038A4DC93%2F20221121%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20221121T201706Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=4a3708594b0413187101d53f13ff98873f06862a9ccac647820231c2796a8721\' WHERE documentid = 4')
    op.execute('UPDATE public."Documents" SET filename = \'1001 Books.pdf\', filepath = \'https://citz-foi-prod.objectstore.gov.bc.ca/dev-forms-foirequests/test/1001%20Books.pdf?response-content-type=application%2Fpdf&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA95AE3AF038A4DC93%2F20221121%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20221121T201604Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=159bcd2e7ad47fc3a2f0bc49ba45306c98ff048778d69fc1d3e24ace7d008528\' WHERE documentid = 5')
    op.execute('UPDATE public."Documents" SET filename = \'6 Important factors.pdf\', filepath = \'https://citz-foi-prod.objectstore.gov.bc.ca/dev-forms-foirequests/test/6%20Important%20factors.pdf?response-content-type=application%2Fpdf&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA95AE3AF038A4DC93%2F20221121%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20221121T201706Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=4a3708594b0413187101d53f13ff98873f06862a9ccac647820231c2796a8721\' WHERE documentid = 6')


def downgrade():
    op.alter_column('Documents', 'filepath',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
    op.execute('UPDATE public."Documents" SET filename = \'sample1.pdf\', filepath = \'/files/sample1.pdf\' WHERE documentid = 1')
    op.execute('UPDATE public."Documents" SET filename = \'sample2.pdf\', filepath = \'/files/sample2.pdf\' WHERE documentid = 2')
    op.execute('UPDATE public."Documents" SET filename = \'sample1.pdf\', filepath = \'/files/sample1.pdf\' WHERE documentid = 3')
    op.execute('UPDATE public."Documents" SET filename = \'sample1.pdf\', filepath = \'/files/sample1.pdf\' WHERE documentid = 4')
    op.execute('UPDATE public."Documents" SET filename = \'sample1.pdf\', filepath = \'/files/sample1.pdf\' WHERE documentid = 5')
    op.execute('UPDATE public."Documents" SET filename = \'sample2.pdf\', filepath = \'/files/sample2.pdf\' WHERE documentid = 6')
