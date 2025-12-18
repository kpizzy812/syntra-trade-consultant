"""add terminal_outcome to trade_outcomes

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2025-12-18

Adds terminal outcome fields to trade_outcomes for EV calculation:
- terminal_outcome: sl/tp1/tp2/tp3/other — max TP hit
- max_tp_reached: 0, 1, 2, или 3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add terminal outcome fields to trade_outcomes."""

    op.add_column(
        'trade_outcomes',
        sa.Column('terminal_outcome', sa.String(10), nullable=True,
                  comment='sl/tp1/tp2/tp3/other — max TP hit')
    )
    op.add_column(
        'trade_outcomes',
        sa.Column('max_tp_reached', sa.Integer(), nullable=True,
                  comment='0, 1, 2, или 3')
    )

    # Add index for terminal_outcome
    op.create_index(
        'ix_trade_outcomes_terminal_outcome',
        'trade_outcomes',
        ['terminal_outcome']
    )


def downgrade() -> None:
    """Remove terminal outcome fields from trade_outcomes."""
    op.drop_index('ix_trade_outcomes_terminal_outcome', table_name='trade_outcomes')
    op.drop_column('trade_outcomes', 'max_tp_reached')
    op.drop_column('trade_outcomes', 'terminal_outcome')
