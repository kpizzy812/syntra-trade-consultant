"""add unrealized R fields to portfolio position

Revision ID: unr34l1z3d
Revises: 60197e3bb98e
Create Date: 2025-12-22

Mark-to-Market для Portfolio Mode:
- unrealized_r: текущий unrealized PnL в R
- mark_price: последняя цена для расчёта
- marked_at: когда обновляли
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'unr34l1z3d'
down_revision: Union[str, Sequence[str], None] = '60197e3bb98e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unrealized R (mark-to-market) fields to PortfolioPosition."""

    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'unrealized_r',
            sa.Float(),
            nullable=True,
            comment='Current unrealized PnL in R (mark-to-market)'
        )
    )

    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'mark_price',
            sa.Float(),
            nullable=True,
            comment='Last mark price used for unrealized calc'
        )
    )

    op.add_column(
        'forward_test_portfolio_positions',
        sa.Column(
            'marked_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='When unrealized_r was last updated'
        )
    )


def downgrade() -> None:
    """Remove unrealized R fields from PortfolioPosition."""

    op.drop_column('forward_test_portfolio_positions', 'marked_at')
    op.drop_column('forward_test_portfolio_positions', 'mark_price')
    op.drop_column('forward_test_portfolio_positions', 'unrealized_r')
