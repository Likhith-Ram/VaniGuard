"""Initial migration

Revision ID: e828a0f0f6cc
Revises: 
Create Date: 2026-09-26 15:16:23.434275

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e828a0f0f6cc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table('users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_phone_number'), 'users', ['phone_number'], unique=True)

    # Trusted Contacts
    op.create_table('trusted_contacts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('contact_name', sa.String(length=100), nullable=False),
        sa.Column('contact_phone', sa.String(length=20), nullable=False),
        sa.Column('relationship', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Telephony Sessions
    op.create_table('telephony_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('caller_phone', sa.String(length=20), nullable=True),
        sa.Column('claimed_identity', sa.String(length=100), nullable=True),
        sa.Column('session_status', sa.Enum('active', 'challenged', 'terminated', 'cleared', name='sessionstatus'), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_telephony_sessions_caller_phone'), 'telephony_sessions', ['caller_phone'], unique=False)

    # Audio Scans
    op.create_table('audio_scans',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=True),
        sa.Column('language', sa.String(length=20), nullable=True),
        sa.Column('impersonation_risk_score', sa.Float(), nullable=False),
        sa.Column('verdict', sa.Enum('genuine', 'suspicious', 'synthetic_clone', name='verdict'), nullable=False),
        sa.Column('audio_sha256', sa.String(length=64), nullable=True),
        sa.Column('spectral_features', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('scanned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['telephony_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audio_scans_audio_sha256'), 'audio_scans', ['audio_sha256'], unique=False)

    # Audit Events
    op.create_table('audit_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('scan_id', sa.UUID(), nullable=True),
        sa.Column('action_triggered', sa.Enum('otp_sent', 'trusted_circle_alerted', 'call_blocked', 'none', name='actiontriggered'), nullable=True),
        sa.Column('payload', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['audio_scans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_index(op.f('ix_audio_scans_audio_sha256'), table_name='audio_scans')
    op.drop_table('audio_scans')
    op.drop_index(op.f('ix_telephony_sessions_caller_phone'), table_name='telephony_sessions')
    op.drop_table('telephony_sessions')
    op.drop_table('trusted_contacts')
    op.drop_index(op.f('ix_users_phone_number'), table_name='users')
    op.drop_table('users')
    op.execute("DROP TYPE actiontriggered")
    op.execute("DROP TYPE verdict")
    op.execute("DROP TYPE sessionstatus")
