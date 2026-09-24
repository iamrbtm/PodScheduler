"""add mail_settings table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'mail_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mail_server', sa.String(200), nullable=False, server_default='localhost'),
        sa.Column('mail_port', sa.Integer(), nullable=False, server_default='25'),
        sa.Column('mail_use_tls', sa.Boolean(), nullable=True),
        sa.Column('mail_use_ssl', sa.Boolean(), nullable=True),
        sa.Column('mail_username', sa.String(200), nullable=True),
        sa.Column('mail_password', sa.String(500), nullable=True),
        sa.Column('mail_default_sender', sa.String(200), nullable=True),
        sa.Column('mail_suppress_send', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], name='fk_mail_settings_updated_by_id'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('mail_settings')
