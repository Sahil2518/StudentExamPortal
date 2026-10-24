"""add_bandit_update

Revision ID: 42d48e9aed16
Revises: 4636861751dd
Create Date: 2026-10-05 17:51:33.272183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '42d48e9aed16'
down_revision: Union[str, None] = '4636861751dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bandit_updates',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('question_attempt_id', UUID(as_uuid=True), nullable=False),
        sa.Column('arm_key', sa.String(), nullable=False),
        sa.Column('outcome', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['question_attempt_id'], ['question_attempts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_attempt_id')
    )
    op.create_index(op.f('ix_bandit_updates_id'), 'bandit_updates', ['id'], unique=False)
    op.create_index(op.f('ix_bandit_updates_question_attempt_id'), 'bandit_updates', ['question_attempt_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_bandit_updates_question_attempt_id'), table_name='bandit_updates')
    op.drop_index(op.f('ix_bandit_updates_id'), table_name='bandit_updates')
    op.drop_table('bandit_updates')
