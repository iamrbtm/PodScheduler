"""add ready_to_distribute podcast status

Revision ID: 9f1c2d3e4b5a
Revises: 77ab1014c239
Create Date: 2026-09-24

"""
from alembic import op

revision = '9f1c2d3e4b5a'
down_revision = '77ab1014c239'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE podcaststatus ADD VALUE IF NOT EXISTS 'ready_to_distribute' BEFORE 'published'")


def downgrade():
    # Postgres cannot drop a single enum value; downgrading would require
    # rebuilding the type. Not supported — recreate the database from a
    # backup taken before this migration if a rollback is truly needed.
    pass
