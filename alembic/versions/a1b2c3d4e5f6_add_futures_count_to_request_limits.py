"""add_futures_count_to_request_limits

Revision ID: a1b2c3d4e5f6
Revises: f8a42c1b3e9d
Create Date: 2025-12-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f8a42c1b3e9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add futures_count column to request_limits table."""
    op.add_column(
        'request_limits',
        sa.Column(
            'futures_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Number of futures signal requests made today'
        )
    )


def downgrade() -> None:
    """Remove futures_count column from request_limits table."""
    op.drop_column('request_limits', 'futures_count')
