"""empty message

Revision ID: cb81f7d5bfca
Revises: a6eaec196523
Create Date: 2022-11-22 10:59:32.352302

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table
from sqlalchemy.sql.sqltypes import Boolean, String
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'cb81f7d5bfca'
down_revision = 'a6eaec196523'
branch_labels = None
depends_on = None
import os

def upgrade():
    s3environment = os.getenv('DEDUPE_S3_ENV')
    docment_path_mapper = table('DocumentPathMapper',
                                 column('category',String),
                                 column('bucket',String),
                                 column('attributes',String),
                                 column('isactive',Boolean),
                                 column('createdby',String),
                                   )
    op.execute('Truncate table public."DocumentPathMapper" RESTART IDENTITY CASCADE;commit;')                               
    op.bulk_insert(
        docment_path_mapper,
        [
            {'category':'Attachments','bucket':'{0}-forms-foirequests-e'.format(s3environment),'isactive':True,'createdby':'System'},
        ]
    )
    op.execute('''INSERT INTO public."DocumentPathMapper"(
            category, bucket, isactive, createdby)
            Select 'Records', lower(bcgovcode) || '-{0}-e' , true, 'System' from
            public."ProgramAreas" where isactive = true'''.format(s3environment))
    op.execute('''INSERT INTO public."DocumentPathMapper"(
            category, bucket, attributes, isactive, createdby)
            VALUES ('Records', 'dev-forms-foirequests-e', '{"s3accesskey":"","s3secretkey":""}', true, 'Richard')''')

def downgrade():
    op.execute('Truncate table public."DocumentPathMapper" RESTART IDENTITY CASCADE;commit;')
