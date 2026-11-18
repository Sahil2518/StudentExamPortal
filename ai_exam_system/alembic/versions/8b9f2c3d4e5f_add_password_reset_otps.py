"""add_password_reset_otps

Revision ID: 8b9f2c3d4e5f
Revises: 7a8e1b2c3d4e
Create Date: 2026-11-18 13:54:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '8b9f2c3d4e5f'
down_revision: Union[str, None] = '7a8e1b2c3d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'password_reset_otps',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('otp_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_otps_email'), 'password_reset_otps', ['email'], unique=False)
    op.create_index(op.f('ix_password_reset_otps_user_id'), 'password_reset_otps', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_password_reset_otps_user_id'), table_name='password_reset_otps')
    op.drop_index(op.f('ix_password_reset_otps_email'), table_name='password_reset_otps')
    op.drop_table('password_reset_otps')
