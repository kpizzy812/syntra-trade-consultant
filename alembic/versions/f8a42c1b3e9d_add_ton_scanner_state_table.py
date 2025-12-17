"""add_ton_scanner_state_table

Revision ID: f8a42c1b3e9d
Revises: e93d58f9a97c
Create Date: 2025-11-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a42c1b3e9d'
down_revision: Union[str, Sequence[str], None] = 'e93d58f9a97c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ton_scanner_states',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('address', sa.String(length=100), nullable=False, comment='TON address being monitored'),
        sa.Column('last_lt', sa.BigInteger(), nullable=False, comment='Logical time of last processed transaction'),
        sa.Column('last_tx_hash', sa.String(length=255), nullable=True, comment='Hash of last processed transaction (for reference)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='State creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, comment='State last update timestamp'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('address')
    )
    op.create_index(op.f('ix_ton_scanner_states_address'), 'ton_scanner_states', ['address'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_ton_scanner_states_address'), table_name='ton_scanner_states')
    op.drop_table('ton_scanner_states')
