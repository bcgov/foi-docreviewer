"""empty message

Revision ID: 641ae620392d
Revises: be8612ebd00e
Create Date: 2023-03-10 14:11:58.092834

"""
from alembic import op
import sqlalchemy as sa
import os


# revision identifiers, used by Alembic.
revision = '641ae620392d'
down_revision = 'be8612ebd00e'
branch_labels = None
depends_on = None


def upgrade():
    s3environment = os.getenv('DEDUPE_S3_ENV')
    op.execute('''INSERT INTO public."DocumentPathMapper"(
            category, bucket, isactive, createdby)
            Select 'Records', lower(bcgovcode) || '-{0}-e' , true, 'System' from
            public."ProgramAreas" where isactive = true and lower(bcgovcode) not in (
            select split_part(bucket, '-', 1) from public."DocumentPathMapper")'''.format(s3environment))


def downgrade():
    pass
