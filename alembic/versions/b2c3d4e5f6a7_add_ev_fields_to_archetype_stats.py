"""add_ev_fields_to_archetype_stats

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-17

Adds EV (Expected Value) support to archetype_stats:
- side column for long/short grouping
- exit_* counts for terminal outcomes
- avg_pnl_r_other for payout_other calculation
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add EV fields to archetype_stats."""

    # === ADD SIDE COLUMN ===
    op.add_column(
        'archetype_stats',
        sa.Column('side', sa.String(10), nullable=True,
                  comment='long/short — критично для EV!')
    )
    op.create_index('ix_archetype_stats_side', 'archetype_stats', ['side'])

    # === ADD TERMINAL OUTCOME COUNTS ===
    op.add_column(
        'archetype_stats',
        sa.Column('exit_sl_count', sa.Integer(), nullable=False,
                  server_default='0', comment='Не дошли ни до одного TP')
    )
    op.add_column(
        'archetype_stats',
        sa.Column('exit_tp1_count', sa.Integer(), nullable=False,
                  server_default='0', comment='Дошли до TP1')
    )
    op.add_column(
        'archetype_stats',
        sa.Column('exit_tp2_count', sa.Integer(), nullable=False,
                  server_default='0', comment='Дошли до TP2')
    )
    op.add_column(
        'archetype_stats',
        sa.Column('exit_tp3_count', sa.Integer(), nullable=False,
                  server_default='0', comment='Дошли до TP3')
    )
    op.add_column(
        'archetype_stats',
        sa.Column('exit_other_count', sa.Integer(), nullable=False,
                  server_default='0', comment='manual/timeout/breakeven ДО любого TP')
    )
    op.add_column(
        'archetype_stats',
        sa.Column('avg_pnl_r_other', sa.Float(), nullable=False,
                  server_default='0', comment='Средний PnL для OTHER исходов')
    )

    # === UPDATE UNIQUE CONSTRAINT ===
    # Drop old constraint
    op.drop_constraint('uq_archetype_group', 'archetype_stats', type_='unique')

    # Create new constraint with side
    op.create_unique_constraint(
        'uq_archetype_group_v2',
        'archetype_stats',
        ['archetype', 'side', 'symbol', 'timeframe', 'volatility_regime']
    )

    # === ADD terminal_outcome TO trade_outcomes ===
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
    op.create_index('ix_outcomes_terminal_outcome', 'trade_outcomes', ['terminal_outcome'])


def downgrade() -> None:
    """Remove EV fields from archetype_stats."""

    # Drop indexes and columns from trade_outcomes
    op.drop_index('ix_outcomes_terminal_outcome', table_name='trade_outcomes')
    op.drop_column('trade_outcomes', 'max_tp_reached')
    op.drop_column('trade_outcomes', 'terminal_outcome')

    # Restore old unique constraint
    op.drop_constraint('uq_archetype_group_v2', 'archetype_stats', type_='unique')
    op.create_unique_constraint(
        'uq_archetype_group',
        'archetype_stats',
        ['archetype', 'symbol', 'timeframe', 'volatility_regime']
    )

    # Drop new columns from archetype_stats
    op.drop_column('archetype_stats', 'avg_pnl_r_other')
    op.drop_column('archetype_stats', 'exit_other_count')
    op.drop_column('archetype_stats', 'exit_tp3_count')
    op.drop_column('archetype_stats', 'exit_tp2_count')
    op.drop_column('archetype_stats', 'exit_tp1_count')
    op.drop_column('archetype_stats', 'exit_sl_count')
    op.drop_index('ix_archetype_stats_side', table_name='archetype_stats')
    op.drop_column('archetype_stats', 'side')
