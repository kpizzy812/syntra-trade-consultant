"""add_stats_system_fields

Revision ID: c3d4e5f6g7h9
Revises: b2c3d4e5f6g8
Create Date: 2025-12-20 12:00:00.000000

Phase 1 Stats System: добавляет поля для статистики и аудита в trade_outcomes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Stats System fields to trade_outcomes."""

    # === Origin & Context ===
    op.add_column('trade_outcomes', sa.Column(
        'origin',
        sa.String(20),
        nullable=True,
        comment='ai_scenario | manual | copy_trade | forward_test'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'exchange',
        sa.String(20),
        nullable=True,
        comment='bybit, binance — для фильтров'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'account_id',
        sa.String(50),
        nullable=True,
        comment='Account ID на бирже'
    ))

    # === Position Size ===
    op.add_column('trade_outcomes', sa.Column(
        'qty',
        sa.Float(),
        nullable=True,
        comment='Количество контрактов/монет'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'notional_usd',
        sa.Float(),
        nullable=True,
        comment='Размер позиции в USD (qty * entry_price)'
    ))

    # === Timing ===
    op.add_column('trade_outcomes', sa.Column(
        'opened_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='Время открытия позиции'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'closed_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='Время закрытия позиции (для сортировки)'
    ))

    # === Fees ===
    op.add_column('trade_outcomes', sa.Column(
        'fees_usd',
        sa.Float(),
        nullable=True,
        comment='Комиссии в USD'
    ))

    # === TP Prices ===
    op.add_column('trade_outcomes', sa.Column(
        'tp1_price',
        sa.Float(),
        nullable=True,
        comment='Цена TP1 на момент входа'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'tp2_price',
        sa.Float(),
        nullable=True,
        comment='Цена TP2 на момент входа'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'tp3_price',
        sa.Float(),
        nullable=True,
        comment='Цена TP3 на момент входа'
    ))

    # === TP Hit Tracking ===
    op.add_column('trade_outcomes', sa.Column(
        'hit_tp1',
        sa.Boolean(),
        nullable=False,
        server_default='false',
        comment='Цена дошла до TP1'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'hit_tp2',
        sa.Boolean(),
        nullable=False,
        server_default='false',
        comment='Цена дошла до TP2'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'hit_tp3',
        sa.Boolean(),
        nullable=False,
        server_default='false',
        comment='Цена дошла до TP3'
    ))

    # === Payload Hash ===
    op.add_column('trade_outcomes', sa.Column(
        'payload_hash',
        sa.String(32),
        nullable=True,
        comment='sha256[:32] канонического payload для детекции рассинхрона'
    ))

    # === Audit & Invalidation ===
    op.add_column('trade_outcomes', sa.Column(
        'invalidated',
        sa.Boolean(),
        nullable=False,
        server_default='false',
        comment='Soft delete flag'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'replaced_by_id',
        sa.Integer(),
        sa.ForeignKey('trade_outcomes.id'),
        nullable=True,
        comment='FK для audit trail при замене записей'
    ))
    op.add_column('trade_outcomes', sa.Column(
        'invalidation_reason',
        sa.String(50),
        nullable=True,
        comment='correction, duplicate_detected, etc.'
    ))

    # === Create Indexes ===
    op.create_index(
        'ix_outcomes_closed_at',
        'trade_outcomes',
        ['closed_at'],
        unique=False
    )
    op.create_index(
        'ix_outcomes_origin_closed',
        'trade_outcomes',
        ['origin', 'closed_at'],
        unique=False
    )
    op.create_index(
        'ix_outcomes_exchange_closed',
        'trade_outcomes',
        ['exchange', 'closed_at'],
        unique=False
    )
    op.create_index(
        'ix_outcomes_origin',
        'trade_outcomes',
        ['origin'],
        unique=False
    )
    op.create_index(
        'ix_outcomes_exchange',
        'trade_outcomes',
        ['exchange'],
        unique=False
    )


def downgrade() -> None:
    """Remove Stats System fields from trade_outcomes."""

    # Drop indexes
    op.drop_index('ix_outcomes_exchange', table_name='trade_outcomes')
    op.drop_index('ix_outcomes_origin', table_name='trade_outcomes')
    op.drop_index('ix_outcomes_exchange_closed', table_name='trade_outcomes')
    op.drop_index('ix_outcomes_origin_closed', table_name='trade_outcomes')
    op.drop_index('ix_outcomes_closed_at', table_name='trade_outcomes')

    # Drop columns (reverse order)
    op.drop_column('trade_outcomes', 'invalidation_reason')
    op.drop_column('trade_outcomes', 'replaced_by_id')
    op.drop_column('trade_outcomes', 'invalidated')
    op.drop_column('trade_outcomes', 'payload_hash')
    op.drop_column('trade_outcomes', 'hit_tp3')
    op.drop_column('trade_outcomes', 'hit_tp2')
    op.drop_column('trade_outcomes', 'hit_tp1')
    op.drop_column('trade_outcomes', 'tp3_price')
    op.drop_column('trade_outcomes', 'tp2_price')
    op.drop_column('trade_outcomes', 'tp1_price')
    op.drop_column('trade_outcomes', 'fees_usd')
    op.drop_column('trade_outcomes', 'closed_at')
    op.drop_column('trade_outcomes', 'opened_at')
    op.drop_column('trade_outcomes', 'notional_usd')
    op.drop_column('trade_outcomes', 'qty')
    op.drop_column('trade_outcomes', 'account_id')
    op.drop_column('trade_outcomes', 'exchange')
    op.drop_column('trade_outcomes', 'origin')
