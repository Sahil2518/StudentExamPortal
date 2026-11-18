"""add_concurrency_composite_indexes

Revision ID: 9c0f3d4e5f6a
Revises: 8b9f2c3d4e5f
Create Date: 2026-11-19 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c0f3d4e5f6a'
down_revision: Union[str, None] = '8b9f2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. High-concurrency query optimization for session lookup by student
    op.create_index(
        'ix_exam_sessions_user_started',
        'exam_sessions',
        ['user_id', 'started_at'],
        unique=False,
        if_not_exists=True
    )
    # 2. Optimization for active domain sessions
    op.create_index(
        'ix_exam_sessions_domain_status',
        'exam_sessions',
        ['domain', 'status'],
        unique=False,
        if_not_exists=True
    )
    # 3. High-throughput question retrieval by sequence number
    op.create_index(
        'ix_session_questions_seq',
        'exam_session_questions',
        ['exam_session_id', 'sequence_number'],
        unique=False,
        if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index('ix_session_questions_seq', table_name='exam_session_questions')
    op.drop_index('ix_exam_sessions_domain_status', table_name='exam_sessions')
    op.drop_index('ix_exam_sessions_user_started', table_name='exam_sessions')
