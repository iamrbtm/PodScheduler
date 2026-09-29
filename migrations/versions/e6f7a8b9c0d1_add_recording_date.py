"""add podcasts.recording_date

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('podcasts', sa.Column('recording_date', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('podcasts', 'recording_date')
