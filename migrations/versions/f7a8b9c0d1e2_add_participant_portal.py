"""add participant portal: participants.portal_token, podcasts.guest_prep_info, guest_questions

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-29

"""
import secrets

from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('participants', sa.Column('portal_token', sa.String(64), nullable=True))
    conn = op.get_bind()
    for (pid,) in conn.execute(sa.text("SELECT id FROM participants")).fetchall():
        conn.execute(
            sa.text("UPDATE participants SET portal_token = :t WHERE id = :i"),
            {"t": secrets.token_urlsafe(32), "i": pid},
        )
    op.create_index('ix_participants_portal_token', 'participants', ['portal_token'], unique=True)

    op.add_column('podcasts', sa.Column('guest_prep_info', sa.Text(), nullable=True))

    op.create_table(
        'guest_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('podcast_participant_id', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['podcast_participant_id'], ['podcast_participants.id'],
                                name='fk_guest_questions_podcast_participant_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_guest_questions_podcast_participant_id', 'guest_questions',
                    ['podcast_participant_id'])


def downgrade():
    op.drop_index('ix_guest_questions_podcast_participant_id', table_name='guest_questions')
    op.drop_table('guest_questions')
    op.drop_column('podcasts', 'guest_prep_info')
    op.drop_index('ix_participants_portal_token', table_name='participants')
    op.drop_column('participants', 'portal_token')
