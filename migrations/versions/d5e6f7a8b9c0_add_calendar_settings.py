"""add calendar_settings table

Revision ID: d5e6f7a8b9c0
Revises: 6e2d6bfd5728
Create Date: 2026-09-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'd5e6f7a8b9c0'
down_revision = '6e2d6bfd5728'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'calendar_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feed_token', sa.String(64), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], name='fk_calendar_settings_updated_by_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('feed_token', name='uq_calendar_settings_feed_token'),
    )


def downgrade():
    op.drop_table('calendar_settings')
