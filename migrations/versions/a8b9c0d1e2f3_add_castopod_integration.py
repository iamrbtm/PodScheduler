"""add castopod settings, show/episode castopod ids, cached stats

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa

revision = 'a8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'castopod_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=True),
        sa.Column('api_username', sa.String(200), nullable=True),
        sa.Column('api_password', sa.String(500), nullable=True),
        sa.Column('sync_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], name='fk_castopod_settings_updated_by_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('shows', sa.Column('castopod_podcast_id', sa.Integer(), nullable=True))
    op.add_column('podcasts', sa.Column('castopod_episode_id', sa.Integer(), nullable=True))
    op.add_column('podcasts', sa.Column('castopod_stats_json', sa.JSON(), nullable=True))
    op.add_column('podcasts', sa.Column('castopod_synced_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('podcasts', 'castopod_synced_at')
    op.drop_column('podcasts', 'castopod_stats_json')
    op.drop_column('podcasts', 'castopod_episode_id')
    op.drop_column('shows', 'castopod_podcast_id')
    op.drop_table('castopod_settings')
