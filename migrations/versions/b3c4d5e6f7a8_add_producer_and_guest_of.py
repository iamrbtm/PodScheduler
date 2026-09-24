"""add producer_id to podcasts and guest_of to podcast_participants

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('podcasts', sa.Column('producer_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_podcasts_producer_id', 'podcasts', 'users', ['producer_id'], ['id']
    )

    op.add_column('podcast_participants', sa.Column('guest_of', sa.String(200), nullable=True))


def downgrade():
    op.drop_column('podcast_participants', 'guest_of')
    op.drop_constraint('fk_podcasts_producer_id', 'podcasts', type_='foreignkey')
    op.drop_column('podcasts', 'producer_id')
