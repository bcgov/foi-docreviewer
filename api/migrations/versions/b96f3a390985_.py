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
            {'name':'new', 'isactive':True, 'description': 'New'},
            {'name':'inprogress', 'isactive':True, 'description': 'In progress'},
            {'name':'saved', 'isactive':True, 'description': 'Saved'}, 
        ]
    )

    documents_table = op.create_table('Documents',
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
        sa.Column('pagecount', sa.Integer(), nullable=True, default=0),
        sa.PrimaryKeyConstraint('documentid', 'version'),
        sa.ForeignKeyConstraint(['statusid'], ['DocumentStatus.statusid'], )
    )

    op.bulk_insert(
        documents_table,
        [
            {'version':1, 'filename':'sample1.pdf','filepath':'/files/','attributes':{},'foiministryrequestid':1,'createdby':{},'updated_at':datetime.now(),'statusid':1,'pagecount':9},
            {'version':1, 'filename':'sample2.pdf','filepath':'/files/','attributes':{},'foiministryrequestid':1,'createdby':{},'updated_at':datetime.now(),'statusid':1,'pagecount':2},
            {'version':1, 'filename':'sample1.pdf','filepath':'/files/','attributes':{},'foiministryrequestid':1,'createdby':{},'updated_at':datetime.now(),'statusid':1,'pagecount':9},
            {'version':1, 'filename':'sample1.pdf','filepath':'/files/','attributes':{},'foiministryrequestid':1,'createdby':{},'updated_at':datetime.now(),'statusid':1,'pagecount':9},
            {'version':1, 'filename':'sample1.pdf','filepath':'/files/','attributes':{},'foiministryrequestid':2,'createdby':{},'updated_at':datetime.now(),'statusid':1,'pagecount':9},
            {'version':1, 'filename':'sample2.pdf','filepath':'/files/','attributes':{},'foiministryrequestid':2,'createdby':{},'updated_at':datetime.now(),'statusid':1,'pagecount':2}
        ]
    )

    document_tag_table = op.create_table('DocumentTags',
        sa.Column('tagid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('documentid', sa.Integer(), nullable=False),
        sa.Column('documentversion', sa.Integer(), nullable=False),
        sa.Column('tag', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('createdby', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.now()),
        sa.PrimaryKeyConstraint('tagid'),
        sa.ForeignKeyConstraint(['documentid', 'documentversion'], ['Documents.documentid', 'Documents.version'], )
    )

    op.bulk_insert(
        document_tag_table,
        [
            {'documentid':1, 'documentversion':1,'tag':{'divisions':[{'divisionid':1}]},'createdby':{}},
            {'documentid':2, 'documentversion':1,'tag':{'divisions':[{'divisionid':1}]},'createdby':{}},
            {'documentid':3, 'documentversion':1,'tag':{'divisions':[{'divisionid':2}]},'createdby':{}},
            {'documentid':4, 'documentversion':1,'tag':{'divisions':[{'divisionid':3}]},'createdby':{}},
            {'documentid':5, 'documentversion':1,'tag':{'divisions':[{'divisionid':1}]},'createdby':{}},
            {'documentid':6, 'documentversion':1,'tag':{'divisions':[{'divisionid':1}]},'createdby':{}}
        ]
    )

    op.create_table('Annotations',
        sa.Column('annotationid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('annotationname', sa.String(length=120), unique=True, nullable=False),
        sa.Column('documentid', sa.Integer(), nullable=False),
        sa.Column('documentversion', sa.Integer(), nullable=False),
        sa.Column('annotation', sa.Text(), nullable=False),
        sa.Column('pagenumber', sa.Integer(), nullable=False),
        sa.Column('isactive', sa.Boolean(), nullable=False, default=True),
        sa.Column('createdby', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.now()),
        sa.Column('updatedby', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
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
            {'name':'Ministry of Advanced Education and Skills Training','type':'BC GOV Ministry','isactive':True,'bcgovcode':'AEST','iaocode':'AED'},
            {'name':'Ministry of Agriculture and Food','type':'BC GOV Ministry','isactive':True,'bcgovcode':'AGR','iaocode':'AGR'},
            {'name':'Ministry of Attorney General','type':'BC GOV Ministry','isactive':True,'bcgovcode':'AG','iaocode':'MAG'},
            {'name':'Ministry of Children and Family Development','type':'BC GOV Ministry','isactive':True,'bcgovcode':'MCF','iaocode':'CFD'},
            {'name':'Ministry of Citizens’ Services','type':'BC GOV Ministry','isactive':True,'bcgovcode':'CITZ','iaocode':'CTZ'},
            {'name':'Ministry of Education and Childcare','type':'BC GOV Ministry','isactive':True,'bcgovcode':'EDU','iaocode':'EDU'},
            {'name':'Ministry of Energy, Mines and Low Carbon Innovation','type':'BC GOV Ministry','isactive':True,'bcgovcode':'EMLI','iaocode':'EML'},
            {'name':'Ministry of Environment and Climate Change Strategy','type':'BC GOV Ministry','isactive':True,'bcgovcode':'ENV','iaocode':'MOE'},
            {'name':'Ministry of Finance','type':'BC GOV Ministry','isactive':True,'bcgovcode':'FIN','iaocode':'FIN'},
            {'name':'Ministry of Forests','type':'BC GOV Ministry','isactive':True,'bcgovcode':'FOR','iaocode':'FOR'},
            {'name':'Ministry of Health','type':'BC GOV Ministry','isactive':True,'bcgovcode':'HLTH','iaocode':'HLTH'},
            {'name':'Ministry of Indigenous Relations and Reconciliation','type':'BC GOV Ministry','isactive':True,'bcgovcode':'IRR','iaocode':'IRR'},
            {'name':'Ministry of Jobs, Economic Recovery and Innovation','type':'BC GOV Ministry','isactive':True,'bcgovcode':'JERI','iaocode':'JER'},
            {'name':'Ministry of Labour','type':'BC GOV Ministry','isactive':True,'bcgovcode':'LBR','iaocode':'LBR'},
            {'name':'Ministry of Mental Health and Addictions','type':'BC GOV Ministry','isactive':True,'bcgovcode':'MMHA','iaocode':'MHA'},
            {'name':'Ministry of Municipal Affairs','type':'BC GOV Ministry','isactive':True,'bcgovcode':'MUNI','iaocode':'MMA'},
            {'name':'Ministry of Public Safety and Solicitor General','type':'BC GOV Ministry','isactive':True,'bcgovcode':'PSSG','iaocode':'PSS'},
            {'name':'Ministry of Social Development and Poverty Reduction','type':'BC GOV Ministry','isactive':True,'bcgovcode':'SDPR','iaocode':'MSD'},
            {'name':'Ministry of Tourism, Arts, Culture and Sport','type':'BC GOV Ministry','isactive':True,'bcgovcode':'TACS','iaocode':'TAC'},
            {'name':'Ministry of Transportation and Infrastructure','type':'BC GOV Ministry','isactive':True,'bcgovcode':'TRAN','iaocode':'TRA'},
            {'name':'BC Coroners Service','type':'Other','isactive':True,'bcgovcode':'OCC','iaocode':'OCC'},
            {'name':'BC Public Service Agency','type':'Other','isactive':True,'bcgovcode':'PSA','iaocode':'PSA'},
            {'name':'Board Resourcing and Development Office','type':'Other','isactive':True,'bcgovcode':'BRD','iaocode':'BRD'},
            {'name':'Community Living BC','type':'Other','isactive':True,'bcgovcode':'CLB','iaocode':'CLB'},
            {'name':'Crown Agencies Secretariat','type':'Other','isactive':True,'bcgovcode':'CAS','iaocode':'CAS'},
            {'name':'Emergency Management BC','type':'Other','isactive':True,'bcgovcode':'EMBC','iaocode':'EMB'},
            {'name':'Environmental Assessment Office','type':'Other','isactive':True,'bcgovcode':'EAO','iaocode':'EAO'},
            {'name':'Government Communications and Public Engagement','type':'Other','isactive':True,'bcgovcode':'GCPE','iaocode':'GCP'},
            {'name':'Independent Investigations Office','type':'Other','isactive':True,'bcgovcode':'IIO','iaocode':'IIO'},
            {'name':'Office of the Premier','type':'Other','isactive':True,'bcgovcode':'PREM','iaocode':'OOP'},
            {'name':'Liquor Distribution Branch','type':'Other','isactive':True,'bcgovcode':'LDB','iaocode':'LDB'},
            {'name':'Transportation Investment Corporation','type':'Other','isactive':True,'bcgovcode':'TIC','iaocode':'TIC'},
            {'name':'Order of British Columbia Advisory Council','type':'Other','isactive':True,'bcgovcode':'OBC','iaocode':'OBC'},
            {'name':'Medal of Good Citizenship Selection Committee','type':'Other','isactive':True,'bcgovcode':'MGC','iaocode':'MGC'},
            {'name':'Declaration Act Secretariat','type':'BC GOV Ministry','isactive':True,'bcgovcode':'DAS','iaocode':'DAS'},
            {'name':'Lands, Water and Resource Stewardship','type':'BC GOV Ministry','isactive':True,'bcgovcode':'LWR','iaocode':'LWR'}
        ]
    )

    programarea_division_table =  op.create_table('ProgramAreaDivisions',
        sa.Column('divisionid', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('programareaid', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('isactive', sa.Boolean(), nullable=False),
        sa.Column('createdby', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('divisionid'),
        sa.ForeignKeyConstraint(['programareaid'], ['ProgramAreas.programareaid'], )
    )

    op.bulk_insert(
        programarea_division_table,
        [
            {'divisionid':1, 'programareaid':6, 'name':'Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':2, 'programareaid':6, 'name':'Deputy Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':3, 'programareaid':6, 'name':'Education Programs', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':4, 'programareaid':6, 'name':'Learning', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':5, 'programareaid':6, 'name':'Services & Technology', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':6, 'programareaid':6, 'name':'Governance & Analytics', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':7, 'programareaid':6, 'name':'Resource Management', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':8, 'programareaid':16, 'name':'Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':9, 'programareaid':16, 'name':'Deputy Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':10, 'programareaid':16, 'name':'Management Services', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':11, 'programareaid':16, 'name':'Immigration Services and Strategic Planning', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':12, 'programareaid':16, 'name':'Local Government', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':13, 'programareaid':14, 'name':'Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':14, 'programareaid':14, 'name':'Deputy Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':15, 'programareaid':14, 'name':'Labour', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':16, 'programareaid':14, 'name':'Management Services', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':17, 'programareaid':14, 'name':'Policy and Legislation', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':18, 'programareaid':14, 'name':'Employment Standards', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':19, 'programareaid':14, 'name':'Workers’ Advisor’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':20, 'programareaid':14, 'name':'Employers’ Advisor’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':21, 'programareaid':13, 'name':'Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':22, 'programareaid':13, 'name':'Deputy Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':23, 'programareaid':13, 'name':'Management Services', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':24, 'programareaid':13, 'name':'Trade & Industry Development', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':25, 'programareaid':13, 'name':'Small Business & Economic Development', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':27, 'programareaid':13, 'name':'Mass Timber Implementation', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':28, 'programareaid':13, 'name':'Innovation, Technology & Investment Capital', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':29, 'programareaid':13, 'name':'Investment & Innovation', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':30, 'programareaid':19, 'name':'Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':31, 'programareaid':19, 'name':'Deputy Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':32, 'programareaid':19, 'name':'Sport and Creative Sector', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':33, 'programareaid':19, 'name':'Management Services', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':34, 'programareaid':19, 'name':'Arts & Culture', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':35, 'programareaid':19, 'name':'Tourism Sector Strategy', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':36, 'programareaid':14, 'name':'Assistant Deputy Minister’s Office', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':37, 'programareaid':6, 'name':'Child Care', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()},
            {'divisionid':38, 'programareaid':6, 'name':'Minister of State', 'isactive':True, 'createdby':'system', 'created_at':datetime.now()}
        ]
    )

    s3_account_table =  op.create_table('OperatingTeamS3ServiceAccounts',
        sa.Column('teamid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('usergroup', sa.String(length=120), nullable=False),
        sa.Column('accesskey', sa.String(length=255), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=120), nullable=False),
        sa.Column('isactive', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('teamid')
    )

    op.bulk_insert(
        s3_account_table,
        [
            {'usergroup':'intake', 'accesskey':'12345', 'secret':'12345', 'type':'iao', 'isactive':True},
            {'usergroup':'flex', 'accesskey':'12345', 'secret':'12345', 'type':'iao', 'isactive':True},
            {'usergroup':'processing', 'accesskey':'12345', 'secret':'12345', 'type':'iao', 'isactive':True},
            {'usergroup':'AEST Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'AGR Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'AG Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'BRD Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'CAS Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'CITZ Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'CLB Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'DAS Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'EAO Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'EDU Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'EMBC Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'EMLI Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'ENV Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'FIN Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'FOR Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'GCPE Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'HLTH Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'IIO Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'IRR Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'JERI Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'LBR Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'LDB Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'LWR Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'MCF Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'MGC Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'MMHA Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'MUNI Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'OBC Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'OCC Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'PREM Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'PSA Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'PSSG Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'SDPR Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'TACS Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'TIC Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True},
            {'usergroup':'TRAN Ministry Team', 'accesskey':'12345', 'secret':'12345', 'type':'ministry', 'isactive':True}
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