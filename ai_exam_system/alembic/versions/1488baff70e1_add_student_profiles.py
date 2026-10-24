"""Add student profiles

Revision ID: 1488baff70e1
Revises: 2229a4297d61
Create Date: 2026-10-05 15:02:00.858136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1488baff70e1'
down_revision: Union[str, Sequence[str], None] = '2229a4297d61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('student_profiles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('qualification', sa.String(), nullable=False),
    sa.Column('branch', sa.String(), nullable=False),
    sa.Column('experience_level', sa.String(), nullable=False),
    sa.Column('preferred_domain', sa.String(), nullable=False),
    sa.Column('preferred_difficulty', sa.String(), nullable=False),
    sa.Column('learning_goal', sa.String(), nullable=False),
    sa.Column('profile_completion', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('student_profiles')
