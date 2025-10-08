"""Rename case table and added new columns

Revision ID: 3970403ad2c7
Revises: cc037068950c
Create Date: 2025-10-06 10:36:04.094004

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '3970403ad2c7'
down_revision = 'cc037068950c'
branch_labels = None
depends_on = None


def upgrade():
    # Rename the table
    #op.rename_table('case', 'cases')

    # Add new columns to the renamed table
    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('descriptions', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('records', sa.Text(), nullable=True))

    # Update foreign key in document table
    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.drop_constraint('document_ibfk_1', type_='foreignkey')
        batch_op.create_foreign_key('document_case_id_fkey', 'cases', ['case_id'], ['id'])


    # ### end Alembic commands ###


def downgrade():
    # Rename the table back from 'casess' to 'case'
    op.rename_table('casess', 'case')

    # Update the foreign key in 'document' to point back to 'case'
    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.drop_constraint('document_case_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key('document_ibfk_1', 'case', ['case_id'], ['id'])
    
    # Optional: recreate index if Alembic dropped it during upgrade
    with op.batch_alter_table('case', schema=None) as batch_op:
        batch_op.create_index('case_number', ['case_number'], unique=True)

    op.create_table('case',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('case_number', mysql.VARCHAR(length=100), nullable=False),
    sa.Column('case_type', mysql.VARCHAR(length=100), nullable=False),
    sa.Column('parties', mysql.TEXT(), nullable=False),
    sa.Column('date_filed', mysql.DATETIME(), nullable=True),
    sa.Column('status', mysql.VARCHAR(length=50), nullable=True),
    sa.Column('handled_by', mysql.VARCHAR(length=150), nullable=True),
    sa.Column('date_closed', mysql.DATETIME(), nullable=True),
    sa.Column('date_paused', mysql.DATETIME(), nullable=True),
    sa.Column('date_resumed', mysql.DATETIME(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )

    '''
    with op.batch_alter_table('case', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('case_number'), ['case_number'], unique=True)

    op.drop_table('casess')
    # ### end Alembic commands ###
    '''