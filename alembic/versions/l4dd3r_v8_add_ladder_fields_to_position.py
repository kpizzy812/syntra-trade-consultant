"""add ladder fields to portfolio position

Revision ID: l4dd3r_v8
Revises: p0rtf0l10m0de
Create Date: 2025-12-22

v8 Ladder Entry & TP:
- remaining_pct: позиция после partial closes
- risk_r_current: текущий риск (после TP1)
- tp_progress: synced с monitor
- realized_r_so_far: накопленный R
- mfe_r, mae_r: денормализация из monitor
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l4dd3r_v8'
down_revision: Union[str, Sequence[str], None] = 'p0rtf0l10m0de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ladder entry/TP fields to PortfolioPosition."""

    # Ladder TP tracking
    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'remaining_pct',
            sa.Float(),
            nullable=False,
            server_default='100.0',
            comment='Remaining position after partial closes (100 -> 70 after TP1)'
        )
    )

    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'risk_r_current',
            sa.Float(),
            nullable=True,
            comment='Current risk = risk_r_filled * remaining_pct / 100'
        )
    )

    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'tp_progress',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='0,1,2,3 - synced from monitor.tp_progress'
        )
    )

    # Unrealized R tracking
    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'realized_r_so_far',
            sa.Float(),
            nullable=False,
            server_default='0.0',
            comment='Synced from monitor.realized_r_so_far'
        )
    )

    # MFE/MAE denormalized from monitor
    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'mfe_r',
            sa.Float(),
            nullable=True,
            comment='Max Favorable Excursion (synced from monitor)'
        )
    )

    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'mae_r',
            sa.Float(),
            nullable=True,
            comment='Max Adverse Excursion (synced from monitor)'
        )
    )

    # Backfill risk_r_current = risk_r_filled for existing positions
    op.execute("""
        UPDATE forward_test_portfolio_positions
        SET risk_r_current = risk_r_filled
        WHERE risk_r_current IS NULL
    """)

    # Make risk_r_current NOT NULL after backfill
    op.alter_column(
        'forward_test_portfolio_positions',
        'risk_r_current',
        nullable=False
    )


def downgrade() -> None:
    """Remove ladder entry/TP fields from PortfolioPosition."""

    op.drop_column('forward_test_portfolio_positions', 'mae_r')
    op.drop_column('forward_test_portfolio_positions', 'mfe_r')
    op.drop_column('forward_test_portfolio_positions', 'realized_r_so_far')
    op.drop_column('forward_test_portfolio_positions', 'tp_progress')
    op.drop_column('forward_test_portfolio_positions', 'risk_r_current')
    op.drop_column('forward_test_portfolio_positions', 'remaining_pct')
