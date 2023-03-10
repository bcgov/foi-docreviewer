"""encryped s3 buckets

Revision ID: 3d6b76fc4f9d
Revises: bef255d2e065
Create Date: 2023-03-08 15:18:19.227058

"""
from alembic import op
import sqlalchemy as sa
import os


# revision identifiers, used by Alembic.
revision = '3d6b76fc4f9d'
down_revision = 'bef255d2e065'
branch_labels = None
depends_on = None


s3environment = os.getenv('DEDUPE_S3_ENV')
# s3environment = 'dev'
print(s3environment)

def upgrade():

    #DocumentPathMapper
    op.execute('''
        DO $BODY$
        DECLARE
            r public."ProgramAreas"%rowtype;
            env text := \'''' + s3environment + '''\';
        BEGIN
            FOR r IN (select * from public."ProgramAreas" where isactive = true)
            LOOP
                update public."DocumentPathMapper" set bucket = REPLACE(bucket, lower(r.bcgovcode || '-' || env), lower(r.bcgovcode || '-' || env || '-e'))
                where bucket = lower(r.bcgovcode || '-' || env);
            END LOOP;
        END; $BODY$
    ''')

    #DocumentPathMapper
    op.execute('''
        DO $BODY$
        DECLARE
            env text := \'''' + s3environment + '''\';
        BEGIN
            update public."DocumentPathMapper" set bucket = env || '-forms-foirequests-e'
            where bucket = env || '-forms-foirequests';
        END; $BODY$
    ''')

    #DocumentDeleted
    op.execute('''
        DO $BODY$
        DECLARE
            r public."ProgramAreas"%rowtype;
            env text := \'''' + s3environment + '''\';
        BEGIN
            FOR r IN (select * from public."ProgramAreas" where isactive = true)
            LOOP
                update public."DocumentDeleted" set filepath = REPLACE(filepath, lower(r.bcgovcode || '-' || env || '/'), lower(r.bcgovcode || '-' || env || '-e/'))
                where filepath like '%' || lower(r.bcgovcode || '-' || env || '/%');
            END LOOP;
        END; $BODY$
    ''')

    #DocumentMaster
    op.execute('''
        DO $BODY$
        DECLARE
            r public."ProgramAreas"%rowtype;
            env text := \'''' + s3environment + '''\';
        BEGIN
            FOR r IN (select * from public."ProgramAreas" where isactive = true)
            LOOP
                update public."DocumentMaster" set filepath = REPLACE(filepath, lower(r.bcgovcode || '-' || env || '/'), lower(r.bcgovcode || '-' || env || '-e/'))
                where filepath like '%' || lower(r.bcgovcode || '-' || env || '/%');
            END LOOP;
        END; $BODY$
    ''')


def downgrade():

    #DocumentPathMapper
    op.execute('''
        DO $BODY$
        DECLARE
            r public."ProgramAreas"%rowtype;
            env text := \'''' + s3environment + '''\';
        BEGIN
            FOR r IN (select * from public."ProgramAreas" where isactive = true)
            LOOP
                update public."DocumentPathMapper" set bucket = REPLACE(bucket, lower(r.bcgovcode || '-' || env || '-e'), lower(r.bcgovcode || '-' || env))
                where bucket = lower(r.bcgovcode || '-' || env || '-e');
            END LOOP;
        END; $BODY$
    ''')

    #DocumentPathMapper
    op.execute('''
        DO $BODY$
        DECLARE
            env text := \'''' + s3environment + '''\';
        BEGIN
            update public."DocumentPathMapper" set bucket = env || '-forms-foirequests'
            where bucket = env || '-forms-foirequests-e';
        END; $BODY$
    ''')

    #DocumentDeleted
    op.execute('''
        DO $BODY$
        DECLARE
            r public."ProgramAreas"%rowtype;
            env text := \'''' + s3environment + '''\';
        BEGIN
            FOR r IN (select * from public."ProgramAreas" where isactive = true)
            LOOP
                update public."DocumentDeleted" set filepath = REPLACE(filepath, lower(r.bcgovcode || '-' || env || '-e/'), lower(r.bcgovcode || '-' || env || '/'))
                where filepath like '%' || lower(r.bcgovcode || '-' || env || '-e/%');
            END LOOP;
        END; $BODY$
    ''')

    #DocumentMaster
    op.execute('''
        DO $BODY$
        DECLARE
            r public."ProgramAreas"%rowtype;
            env text := \'''' + s3environment + '''\';
        BEGIN
            FOR r IN (select * from public."ProgramAreas" where isactive = true)
            LOOP
                update public."DocumentMaster" set filepath = REPLACE(filepath, lower(r.bcgovcode || '-' || env || '-e/'), lower(r.bcgovcode || '-' || env || '/'))
                where filepath like '%' || lower(r.bcgovcode || '-' || env || '-e/%');
            END LOOP;
        END; $BODY$
    ''')