"""add_live_entrance_exam_fields

Revision ID: 7a8e1b2c3d4e
Revises: 42d48e9aed16
Create Date: 2026-10-24 16:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7a8e1b2c3d4e'
down_revision: Union[str, None] = '42d48e9aed16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add live exam fields to exam_sessions
    op.add_column('exam_sessions', sa.Column('exam_type', sa.String(length=20), server_default='practice', nullable=False))
    op.add_column('exam_sessions', sa.Column('positive_mark', sa.Float(), server_default='4.0', nullable=False))
    op.add_column('exam_sessions', sa.Column('negative_mark', sa.Float(), server_default='1.0', nullable=False))
    op.add_column('exam_sessions', sa.Column('negative_marks_total', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('exam_sessions', sa.Column('raw_score', sa.Float(), nullable=True))
    op.add_column('exam_sessions', sa.Column('exam_paper_title', sa.String(length=255), nullable=True))

    # Add palette & review status fields to exam_session_questions
    op.add_column('exam_session_questions', sa.Column('review_status', sa.String(length=30), server_default='not_visited', nullable=False))
    op.add_column('exam_session_questions', sa.Column('selected_option', sa.String(length=500), nullable=True))
    op.add_column('exam_session_questions', sa.Column('is_correct', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('exam_session_questions', 'is_correct')
    op.drop_column('exam_session_questions', 'selected_option')
    op.drop_column('exam_session_questions', 'review_status')

    op.drop_column('exam_sessions', 'exam_paper_title')
    op.drop_column('exam_sessions', 'raw_score')
    op.drop_column('exam_sessions', 'negative_marks_total')
    op.drop_column('exam_sessions', 'negative_mark')
    op.drop_column('exam_sessions', 'positive_mark')
    op.drop_column('exam_sessions', 'exam_type')
