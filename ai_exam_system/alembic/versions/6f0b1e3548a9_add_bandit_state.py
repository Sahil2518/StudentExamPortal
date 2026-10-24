"""Add bandit_state

Revision ID: 6f0b1e3548a9
Revises: 1488baff70e1
Create Date: 2026-10-05 15:57:13.435422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f0b1e3548a9'
down_revision: Union[str, Sequence[str], None] = '1488baff70e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('bandit_states',
    sa.Column('arm_key', sa.String(), nullable=False),
    sa.Column('alpha', sa.Float(), nullable=False),
    sa.Column('beta', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('arm_key')
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('bandit_states')
