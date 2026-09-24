"""add episode audio fields to podcasts

Revision ID: 77ab1014c239
Revises: 434bbcd868e3
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = '77ab1014c239'
down_revision = '434bbcd868e3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('podcasts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('audio_object_key', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('audio_url', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('audio_duration_seconds', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('audio_file_size', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('episode_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('season_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('published_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('podcasts', schema=None) as batch_op:
        batch_op.drop_column('published_at')
        batch_op.drop_column('season_number')
        batch_op.drop_column('episode_number')
        batch_op.drop_column('audio_file_size')
        batch_op.drop_column('audio_duration_seconds')
        batch_op.drop_column('audio_url')
        batch_op.drop_column('audio_object_key')
