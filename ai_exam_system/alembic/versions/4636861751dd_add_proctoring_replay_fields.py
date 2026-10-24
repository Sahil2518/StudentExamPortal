"""Add proctoring replay fields

Revision ID: 4636861751dd
Revises: 6f0b1e3548a9
Create Date: 2026-10-05 16:19:13.454708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4636861751dd'
down_revision: Union[str, Sequence[str], None] = '6f0b1e3548a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('proctoring_events', sa.Column('client_event_id', sa.String(length=100), nullable=True))
    op.add_column('proctoring_events', sa.Column('sequence_number', sa.Integer(), nullable=True))
    op.create_unique_constraint('uq_proctoring_client_event_id', 'proctoring_events', ['client_event_id'])

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_proctoring_client_event_id', 'proctoring_events', type_='unique')
    op.drop_column('proctoring_events', 'sequence_number')
    op.drop_column('proctoring_events', 'client_event_id')
