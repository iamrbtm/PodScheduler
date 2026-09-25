"""fix participant_role to use a native Postgres enum

The `participant_role` column has been a plain VARCHAR(20) since it was
added in a1b2c3d4e5f6, but the model (app/models/podcast_participant.py)
declares it as `db.Enum(ParticipantRole, ...)`. SQLAlchemy's Postgres
dialect binds enum-typed columns with an explicit `::participantrole`
cast, so every INSERT into podcast_participants fails with
`type "participantrole" does not exist` against a database built from
just the checked-in migrations. This creates that type and converts the
column to it, matching what the model has expected all along.

Revision ID: 6e2d6bfd5728
Revises: 1bc3240f57d3
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa

revision = '6e2d6bfd5728'
down_revision = '1bc3240f57d3'
branch_labels = None
depends_on = None

participant_role_enum = sa.Enum('keynote_speaker', 'roundtable', name='participantrole')


def upgrade():
    bind = op.get_bind()
    participant_role_enum.create(bind, checkfirst=True)
    op.execute(
        "ALTER TABLE podcast_participants "
        "ALTER COLUMN participant_role TYPE participantrole "
        "USING participant_role::participantrole"
    )


def downgrade():
    op.execute(
        "ALTER TABLE podcast_participants "
        "ALTER COLUMN participant_role TYPE VARCHAR(20) "
        "USING participant_role::text"
    )
    participant_role_enum.drop(op.get_bind(), checkfirst=True)
