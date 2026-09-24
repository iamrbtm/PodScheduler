"""rename guests to participants, add participant roles, add email templates

Revision ID: a1b2c3d4e5f6
Revises: f2d535a367fc
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f2d535a367fc'
branch_labels = None
depends_on = None


def upgrade():
    # Create email_templates table first (referenced by podcast_participants)
    op.create_table(
        'email_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False, server_default=''),
        sa.Column('blocks_json', sa.Text(), nullable=True),
        sa.Column('html_body', sa.Text(), nullable=True),
        sa.Column('text_body', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Rename guests -> participants
    op.execute('ALTER TABLE guests RENAME TO participants')

    # Rename podcast_guests -> podcast_participants
    op.execute('ALTER TABLE podcast_guests RENAME TO podcast_participants')

    # Rename guest_id column to participant_id
    op.execute('ALTER TABLE podcast_participants RENAME COLUMN guest_id TO participant_id')

    # Add participant_role column
    op.add_column('podcast_participants',
        sa.Column('participant_role', sa.String(20), nullable=True))
    op.execute("UPDATE podcast_participants SET participant_role = 'roundtable'")
    op.alter_column('podcast_participants', 'participant_role', nullable=False)

    # Add email_template_id FK to podcast_participants
    op.add_column('podcast_participants',
        sa.Column('email_template_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_podcast_participants_email_template',
        'podcast_participants', 'email_templates',
        ['email_template_id'], ['id']
    )

    # Rename unique constraint
    op.execute('ALTER TABLE podcast_participants RENAME CONSTRAINT uq_podcast_guest TO uq_podcast_participant')


def downgrade():
    op.drop_constraint('fk_podcast_participants_email_template', 'podcast_participants', type_='foreignkey')
    op.drop_column('podcast_participants', 'email_template_id')
    op.drop_column('podcast_participants', 'participant_role')
    op.execute('ALTER TABLE podcast_participants RENAME COLUMN participant_id TO guest_id')
    op.execute('ALTER TABLE podcast_participants RENAME TO podcast_guests')
    op.execute('ALTER TABLE participants RENAME TO guests')
    op.drop_table('email_templates')
