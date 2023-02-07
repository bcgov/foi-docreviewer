"""empty message

Revision ID: fa372bcf451e
Revises: b9ecac992673
Create Date: 2023-01-30 14:49:39.093465

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa372bcf451e'
down_revision = 'b9ecac992673'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('DocumentMaster',
        sa.Column('documentmasterid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('filepath', sa.String(length=500), nullable=False), 
        sa.Column('ministryrequestid', sa.Integer(), nullable=False),
        sa.Column('recordid', sa.Integer(), nullable=True),
        sa.Column('processingparentid', sa.Integer(), nullable=True),
        sa.Column('parentid', sa.Integer(), nullable=True),
        sa.Column('isredactionready', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('createdby', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updatedby', sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint('documentmasterid')
    )

    op.execute('''alter table public."FileConversionJob" add inputdocumentmasterid integer;''')
    op.execute('''alter table public."FileConversionJob" drop column inputfilepath;''')
    op.execute('''alter table public."FileConversionJob" add outputdocumentmasterid integer;''')
    op.execute('''alter table public."FileConversionJob" drop column outputfilepath;''')
    op.execute('''alter table public."FileConversionJob" drop column parentfilepath;''')
    op.execute('''alter table public."FileConversionJob" drop column parentfilename;''')
    op.execute('''alter table public."DeduplicationJob" add documentmasterid integer;''')
    op.execute('''alter table public."DeduplicationJob" drop column filepath;''')
    op.execute('''alter table public."Documents" add documentmasterid integer;''')
    op.execute('''alter table public."Documents" drop column filepath;''')
    op.execute('''alter table public."DocumentTags" rename to "DocumentAttributes";''')
    op.execute('''alter table public."DocumentAttributes" drop column documentversion;''')
    op.execute('''alter table public."DocumentAttributes" rename column tagid to attributeid;''')
    op.execute('''alter table public."DocumentAttributes" rename column tag to attributes;''')
    op.execute('''alter table public."DocumentAttributes" rename column documentid to documentmasterid;''')
    op.execute('''alter table public."DocumentAttributes" alter column created_at set default now();''')


def downgrade():
    op.execute('''alter table public."FileConversionJob" drop column inputdocumentmasterid;''')
    op.execute('''alter table public."FileConversionJob" add inputfilepath varchar(240);''')
    op.execute('''alter table public."FileConversionJob" drop column outputdocumentmasterid ;''')
    op.execute('''alter table public."FileConversionJob" add outputfilepath varchar(240);''')
    op.execute('''alter table public."FileConversionJob" add parentfilepath varchar(240);''')
    op.execute('''alter table public."FileConversionJob" add parentfilename varchar(500);''')
    op.execute('''alter table public."DeduplicationJob" drop column documentmasterid;''')
    op.execute('''alter table public."DeduplicationJob" add filepath varchar(240);''')
    op.execute('''alter table public."Documents" drop column documentmasterid;''')
    op.execute('''alter table public."Documents" add filepath varchar(240);''')
    op.execute('''drop table public."DocumentMaster";''')
    op.execute('''alter table public."DocumentAttributes" rename to "DocumentTags";''')
    op.execute('''alter table public."DocumentTags" add column documentversion integer default 1;''')
    op.execute('''alter table public."DocumentTags" alter column test drop default;''')
    op.execute('''alter table public."DocumentAttributes" rename column attributeid to tagid;''')
    op.execute('''alter table public."DocumentAttributes" rename column attributes to tag;''')
    op.execute('''alter table public."DocumentAttributes" rename column documentmasterid to documentid;''')
    op.execute('''alter table public."DocumentAttributes" alter column created_at drop default;''')
