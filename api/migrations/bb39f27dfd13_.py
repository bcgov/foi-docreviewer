"""Govt BC Organization Changes Nov 20, 2026 (Provincial Elections)

Revision ID: bb39f27dfd13
Revises: d3de6e5bea18
Create Date: 2026-11-21 00:02:15.847432

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import os

# revision identifiers, used by Alembic.
revision = 'bb39f27dfd13'
down_revision = 'd3de6e5bea18'
branch_labels = None
depends_on = None

ENVIRONMENT = os.getenv('OSS_S3_ENVIRONMENT') or 'dev'
access = os.getenv('OSS_S3_FORMS_ACCESS_KEY_ID') or ""
secret = os.getenv('OSS_S3_FORMS_SECRET_ACCESS_KEY') or ""
s3accesskeyjson = f'{{"s3accesskey": "{access}", "s3secretkey": "{secret}"}}'
NEW_MINISTRIES = ["edt", "emp", "lhs"]

def upgrade():
    connection = op.get_bind()
    for org in NEW_MINISTRIES:
        bucket_name = org + f"-{ENVIRONMENT}-e"
        # DocumentPathMapper
        statement = sa.text('''
                        INSERT INTO public."DocumentPathMapper" (category, bucket, attributes, isactive, createdby)
                        VALUES ('Records', :bucket_name, :s3accesskeyjson, TRUE, 'System')
                    ''')
        params = {'bucket_name': bucket_name, 's3accesskeyjson': s3accesskeyjson}
        connection.execute(statement, params)

def downgrade():
    connection = op.get_bind()
    for org in reversed(NEW_MINISTRIES):
        bucket_name = org + f"-{ENVIRONMENT}-e"
        statement = sa.text('''
                DELETE FROM public."DocumentPathMapper"
                WHERE category = 'Records' AND bucket = :bucket_name
                  AND createdby = 'System'
            ''')
        params = {'bucket_name': bucket_name}
        connection.execute(statement, params)
