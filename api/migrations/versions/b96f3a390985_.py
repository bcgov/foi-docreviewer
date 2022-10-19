"""empty message

Revision ID: b96f3a390985
Revises: 
Create Date: 2022-10-11 12:02:04.313388

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'b96f3a390985'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    document_status_table = op.create_table('DocumentStatus',
        sa.Column('statusid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('isactive', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('statusid')
    )

    op.bulk_insert(
        document_status_table,
        [
            {'name':'unread', 'isactive':True, 'description': 'Unread'},
            {'name':'inprogress', 'isactive':True, 'description': 'In progress'},
            {'name':'saved', 'isactive':True, 'description': 'Saved'}, 
        ]
    )

    op.create_table('Documents',
        sa.Column('documentid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('version', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('filename', sa.String(length=120), nullable=False),
        sa.Column('filepath', sa.String(length=255), nullable=False),
        sa.Column('attributes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('foiministryrequestid', sa.Integer(), nullable=False),
        sa.Column('createdby', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.now()),
        sa.Column('updatedby', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('statusid', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('documentid', 'version'),
        sa.ForeignKeyConstraint(['statusid'], ['DocumentStatus.statusid'], )
    )

    op.create_table('DocumentTags',
        sa.Column('tagid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('documentid', sa.Integer(), nullable=False),
        sa.Column('documentversion', sa.Integer(), nullable=False),
        sa.Column('tag', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('createdby', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.now()),
        sa.PrimaryKeyConstraint('tagid'),
        sa.ForeignKeyConstraint(['documentid', 'documentversion'], ['Documents.documentid', 'Documents.version'], )
    )

    op.create_table('Annotations',
        sa.Column('annotationid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('documentid', sa.Integer(), nullable=False),
        sa.Column('documentversion', sa.Integer(), nullable=False),
        sa.Column('annotation', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('pagenumber', sa.Integer(), nullable=True),
        sa.Column('createdby', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.now()),
        sa.PrimaryKeyConstraint('annotationid'),
        sa.ForeignKeyConstraint(['documentid', 'documentversion'], ['Documents.documentid', 'Documents.version'], )
    )

    program_areas_table =  op.create_table('ProgramAreas',
        sa.Column('programareaid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('type', sa.String(length=120), nullable=False),
        sa.Column('bcgovcode', sa.String(length=120), nullable=False),
        sa.Column('iaocode', sa.String(length=120), nullable=False),
        sa.Column('isactive', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('programareaid')
    )

    op.bulk_insert(
        program_areas_table,
        [
            {'name':'test', 'type':'iao', 'bcgovcode':'iao', 'iaocode':'iao', 'isactive':True},
        ]
    )

    programarea_division_table =  op.create_table('ProgramAreaDivisions',
        sa.Column('divisionid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('programareaid', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('isactive', sa.Boolean(), nullable=False),
        sa.Column('createdby', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('divisionid'),
        sa.ForeignKeyConstraint(['programareaid'], ['ProgramAreas.programareaid'], )
    )

    # op.bulk_insert(
    #     programarea_division_table,
    #     [
    #         {'programareaid':1, 'name':'', 'isactive':True, 'createdby':'', 'created_at':''},
    #     ]
    # )

    s3_account_table =  op.create_table('OperatingTeamS3ServiceAccounts',
        sa.Column('teamid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('accesskey', sa.String(length=255), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('type', sa.String(length=120), nullable=False),
        sa.Column('isactive', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('teamid')
    )

    op.bulk_insert(
        s3_account_table,
        [
            {'accesskey':'12345', 'secret':'12345', 'name':'test', 'type':'test', 'isactive':True},
        ]
    )

    docment_path_mapper = op.create_table('DocumentPathMapper',
        sa.Column('documentpathid', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('category', sa.Text,nullable=False),
        sa.Column('bucket', sa.Text,nullable=False),
        sa.Column('attributes', sa.Text,nullable=True),
        sa.Column('isactive', sa.Boolean(), nullable=False),
        sa.Column('createdby', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.now()),
        sa.Column('updatedby', sa.String(length=120), nullable=True), 
        sa.Column('updated_at', sa.DateTime(), nullable=True),   
        sa.PrimaryKeyConstraint('documentpathid')
    )

    op.bulk_insert(
        docment_path_mapper,
        [
            {'category':'Attachments','bucket':'$environment-forms-foirequests','isactive':True,'createdby':'System'},
            {'category':'Records','bucket':'$bcgovcode-$environment','isactive':True,'createdby':'System'}
        ]
    )

def downgrade():
    op.drop_table('Documents')
    op.drop_table('DocumentTags')
    op.drop_table('DocumentStatus')
    op.drop_table('Annotations')
    op.drop_table('ProgramAreas')
    op.drop_table('ProgramAreaDivisions')
    op.drop_table('OperatingTeamS3ServiceAccounts')
    op.drop_table('DocumentPathMapper')