"""add_watchlist_table

Revision ID: e93d58f9a97c
Revises: eebdf7a268e8
Create Date: 2025-11-18 10:31:41.271388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e93d58f9a97c'
down_revision: Union[str, Sequence[str], None] = 'eebdf7a268e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'watchlists',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='User ID (foreign key)'),
        sa.Column('coin_id', sa.String(length=100), nullable=False, comment="CoinGecko coin ID (e.g., 'bitcoin', 'ethereum')"),
        sa.Column('symbol', sa.String(length=20), nullable=False, comment="Coin symbol (e.g., 'BTC', 'ETH')"),
        sa.Column('name', sa.String(length=100), nullable=False, comment="Coin name (e.g., 'Bitcoin', 'Ethereum')"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='Added to watchlist timestamp'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'coin_id', name='uq_user_coin')
    )
    op.create_index(op.f('ix_watchlists_user_id'), 'watchlists', ['user_id'], unique=False)
    op.create_index(op.f('ix_watchlists_coin_id'), 'watchlists', ['coin_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_watchlists_coin_id'), table_name='watchlists')
    op.drop_index(op.f('ix_watchlists_user_id'), table_name='watchlists')
    op.drop_table('watchlists')
