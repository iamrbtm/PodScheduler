"""add directory_submissions table

Revision ID: 1bc3240f57d3
Revises: 9f1c2d3e4b5a
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = '1bc3240f57d3'
down_revision = '9f1c2d3e4b5a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'directory_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('show_id', sa.Integer(), nullable=False),
        sa.Column('directory_key', sa.String(50), nullable=False),
        sa.Column('status', sa.Enum('not_submitted', 'submitted', 'live', name='submissionstatus'), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['show_id'], ['shows.id'], name='fk_directory_submissions_show_id'),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], name='fk_directory_submissions_updated_by_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('show_id', 'directory_key', name='uq_directory_submission_show_key'),
    )


def downgrade():
    op.drop_table('directory_submissions')
    sa.Enum(name='submissionstatus').drop(op.get_bind(), checkfirst=True)
