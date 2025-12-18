"""add EV v2 path outcome fields

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2025-12-18

Adds V2 outcome tracking fields to archetype_stats for path-based EV calculation:
- exit_sl_early_count: SL до TP1 (полный лосс -1R)
- exit_be_after_tp1_count: BE hit после TP1
- exit_stop_in_profit_count: Trail/lock profit после TP1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add V2 path outcome fields to archetype_stats."""

    # === V2 PATH OUTCOME COUNTS ===
    op.add_column(
        'archetype_stats',
        sa.Column('exit_sl_early_count', sa.Integer(), nullable=True,
                  comment='SL до TP1 (полный лосс -1R)')
    )
    op.add_column(
        'archetype_stats',
        sa.Column('exit_be_after_tp1_count', sa.Integer(), nullable=True,
                  comment='BE hit после TP1')
    )
    op.add_column(
        'archetype_stats',
        sa.Column('exit_stop_in_profit_count', sa.Integer(), nullable=True,
                  comment='Trail/lock profit после TP1')
    )


def downgrade() -> None:
    """Remove V2 path outcome fields from archetype_stats."""
    op.drop_column('archetype_stats', 'exit_stop_in_profit_count')
    op.drop_column('archetype_stats', 'exit_be_after_tp1_count')
    op.drop_column('archetype_stats', 'exit_sl_early_count')
