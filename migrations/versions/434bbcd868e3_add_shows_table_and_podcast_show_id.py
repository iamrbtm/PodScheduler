"""add shows table and podcast show_id

Revision ID: 434bbcd868e3
Revises: c4d5e6f7a8b9
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = '434bbcd868e3'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'shows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('feed_slug', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('author_name', sa.String(200), nullable=False),
        sa.Column('owner_email', sa.String(200), nullable=False),
        sa.Column('itunes_category', sa.String(100), nullable=False, server_default='Technology'),
        sa.Column('explicit', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('language', sa.String(10), nullable=False, server_default='en-us'),
        sa.Column('website_url', sa.String(500), nullable=True),
        sa.Column('cover_image_object_key', sa.String(500), nullable=True),
        sa.Column('cover_image_url', sa.String(500), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name='fk_shows_created_by_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('feed_slug', name='uq_shows_feed_slug'),
    )

    with op.batch_alter_table('podcasts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('show_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_podcasts_show_id', 'shows', ['show_id'], ['id'])


def downgrade():
    with op.batch_alter_table('podcasts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_podcasts_show_id', type_='foreignkey')
        batch_op.drop_column('show_id')

    op.drop_table('shows')
