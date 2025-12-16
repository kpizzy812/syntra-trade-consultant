"""add_feedback_learning_tables

Revision ID: a1b2c3d4e5f6
Revises: 25b05c9afc92
Create Date: 2025-12-17 00:56:49

Adds tables for feedback loop and learning system:
- trade_outcomes: Stores trade results with full telemetry
- confidence_buckets: Aggregated stats for confidence calibration
- archetype_stats: Performance stats per trade archetype
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '25b05c9afc92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create feedback loop and learning tables."""

    # ===========================================
    # TABLE: trade_outcomes
    # ===========================================
    op.create_table(
        'trade_outcomes',
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # 4 ключа склейки
        sa.Column('trade_id', sa.String(50), nullable=False,
                  comment='UUID от бота (unique)'),
        sa.Column('analysis_id', sa.String(50), nullable=False,
                  comment='UUID от Syntra /futures-scenarios'),
        sa.Column('scenario_local_id', sa.Integer(), nullable=False,
                  comment='1..N в рамках analysis'),
        sa.Column('scenario_hash', sa.String(64), nullable=False,
                  comment='sha256 от scenario snapshot'),

        # Idempotency
        sa.Column('idempotency_key', sa.String(100), nullable=False,
                  comment='{trade_id}:{event_type}'),

        # Context
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False,
                  comment='Long | Short'),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('is_testnet', sa.Boolean(), nullable=False, default=False,
                  comment='Фильтр для learning'),

        # Exit
        sa.Column('exit_reason', sa.String(20), nullable=True,
                  comment='tp1, tp2, sl, manual, etc.'),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('exit_timestamp', sa.DateTime(timezone=True), nullable=True),

        # PnL
        sa.Column('pnl_usd', sa.Float(), nullable=True),
        sa.Column('pnl_r', sa.Float(), nullable=True,
                  comment='PnL / risk'),
        sa.Column('roe_pct', sa.Float(), nullable=True,
                  comment='PnL / margin * 100'),

        # MAE/MFE
        sa.Column('mae_r', sa.Float(), nullable=True,
                  comment='Max Adverse Excursion in R'),
        sa.Column('mfe_r', sa.Float(), nullable=True,
                  comment='Max Favorable Excursion in R'),
        sa.Column('capture_efficiency', sa.Float(), nullable=True,
                  comment='pnl / mfe'),

        # Time metrics
        sa.Column('time_in_trade_min', sa.Integer(), nullable=True),
        sa.Column('time_to_mfe_min', sa.Integer(), nullable=True,
                  comment='Минут до макс profit'),
        sa.Column('time_to_mae_min', sa.Integer(), nullable=True,
                  comment='Минут до макс drawdown'),
        sa.Column('post_sl_mfe_r', sa.Float(), nullable=True,
                  comment='MFE после SL (если SL был неправильным)'),

        # Confidence
        sa.Column('confidence_raw', sa.Float(), nullable=True,
                  comment='Оригинальный AI confidence'),
        sa.Column('confidence_calibrated', sa.Float(), nullable=True,
                  comment='Калиброванный confidence'),

        # Archetype
        sa.Column('primary_archetype', sa.String(50), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='["tag1", "tag2"]'),
        sa.Column('label', sa.String(20), nullable=True,
                  comment='win, loss, breakeven'),

        # JSONB data
        sa.Column('execution_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='Execution Report (слой B)'),
        sa.Column('attribution_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='Attribution (слой D)'),
        sa.Column('scenario_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='Полный snapshot сценария'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),

        # Primary key
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for trade_outcomes
    op.create_index('ix_outcomes_trade_id', 'trade_outcomes', ['trade_id'], unique=True)
    op.create_index('ix_outcomes_idempotency', 'trade_outcomes', ['idempotency_key'], unique=True)
    op.create_index('ix_outcomes_analysis_id', 'trade_outcomes', ['analysis_id'])
    op.create_index('ix_outcomes_user_id', 'trade_outcomes', ['user_id'])
    op.create_index('ix_outcomes_symbol', 'trade_outcomes', ['symbol'])
    op.create_index('ix_outcomes_timeframe', 'trade_outcomes', ['timeframe'])
    op.create_index('ix_outcomes_is_testnet', 'trade_outcomes', ['is_testnet'])
    op.create_index('ix_outcomes_exit_reason', 'trade_outcomes', ['exit_reason'])
    op.create_index('ix_outcomes_confidence_raw', 'trade_outcomes', ['confidence_raw'])
    op.create_index('ix_outcomes_primary_archetype', 'trade_outcomes', ['primary_archetype'])
    op.create_index('ix_outcomes_label', 'trade_outcomes', ['label'])

    # Composite indexes
    op.create_index('ix_outcomes_user_created', 'trade_outcomes', ['user_id', 'created_at'])
    op.create_index('ix_outcomes_symbol_tf', 'trade_outcomes', ['symbol', 'timeframe', 'created_at'])
    op.create_index('ix_outcomes_archetype_created', 'trade_outcomes', ['primary_archetype', 'created_at'])

    # ===========================================
    # TABLE: confidence_buckets
    # ===========================================
    op.create_table(
        'confidence_buckets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # Bucket definition
        sa.Column('bucket_name', sa.String(20), nullable=False,
                  comment='e.g., "0.55-0.70"'),
        sa.Column('confidence_min', sa.Float(), nullable=False),
        sa.Column('confidence_max', sa.Float(), nullable=False),

        # Statistics
        sa.Column('total_trades', sa.Integer(), nullable=False, default=0),
        sa.Column('wins', sa.Integer(), nullable=False, default=0),
        sa.Column('losses', sa.Integer(), nullable=False, default=0),
        sa.Column('breakevens', sa.Integer(), nullable=False, default=0),

        # Winrate
        sa.Column('actual_winrate_raw', sa.Float(), nullable=False, default=0,
                  comment='wins / total'),
        sa.Column('actual_winrate_smoothed', sa.Float(), nullable=False, default=0,
                  comment='Laplace: (wins + 1) / (total + 2)'),

        # Additional metrics
        sa.Column('avg_pnl_r', sa.Float(), nullable=False, default=0),
        sa.Column('avg_mae_r', sa.Float(), nullable=False, default=0),
        sa.Column('avg_mfe_r', sa.Float(), nullable=False, default=0),

        # Calibration
        sa.Column('calibration_offset', sa.Float(), nullable=False, default=0,
                  comment='smoothed_winrate - bucket_midpoint'),

        # Meta
        sa.Column('sample_size', sa.Integer(), nullable=False, default=0,
                  comment='Размер выборки для расчёта'),
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_confidence_buckets_name', 'confidence_buckets', ['bucket_name'], unique=True)

    # ===========================================
    # TABLE: archetype_stats
    # ===========================================
    op.create_table(
        'archetype_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # Grouping
        sa.Column('archetype', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=True,
                  comment='None = все символы'),
        sa.Column('timeframe', sa.String(10), nullable=True,
                  comment='None = все TF'),
        sa.Column('volatility_regime', sa.String(10), nullable=True,
                  comment='low/normal/high или None'),

        # Statistics
        sa.Column('total_trades', sa.Integer(), nullable=False, default=0),
        sa.Column('wins', sa.Integer(), nullable=False, default=0),
        sa.Column('losses', sa.Integer(), nullable=False, default=0),
        sa.Column('winrate', sa.Float(), nullable=False, default=0),
        sa.Column('avg_pnl_r', sa.Float(), nullable=False, default=0),
        sa.Column('profit_factor', sa.Float(), nullable=False, default=0,
                  comment='gross_profit / gross_loss'),

        # MAE/MFE
        sa.Column('avg_mae_r', sa.Float(), nullable=False, default=0),
        sa.Column('avg_mfe_r', sa.Float(), nullable=False, default=0),
        sa.Column('p75_mae_r', sa.Float(), nullable=False, default=0,
                  comment='75th percentile MAE'),
        sa.Column('p90_mae_r', sa.Float(), nullable=False, default=0,
                  comment='90th percentile MAE'),
        sa.Column('p50_mfe_r', sa.Float(), nullable=False, default=0,
                  comment='median MFE'),

        # Optimization suggestions
        sa.Column('suggested_sl_atr_mult', sa.Float(), nullable=False, default=1.0,
                  comment='SL = X * ATR'),
        sa.Column('suggested_tp1_r', sa.Float(), nullable=False, default=1.5),
        sa.Column('suggested_tp2_r', sa.Float(), nullable=False, default=2.5),

        # Meta
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_archetype_stats_archetype', 'archetype_stats', ['archetype'])
    op.create_unique_constraint(
        'uq_archetype_group',
        'archetype_stats',
        ['archetype', 'symbol', 'timeframe', 'volatility_regime']
    )

    # ===========================================
    # INSERT DEFAULT CONFIDENCE BUCKETS
    # ===========================================
    op.execute("""
        INSERT INTO confidence_buckets (bucket_name, confidence_min, confidence_max, total_trades, wins, losses, breakevens, actual_winrate_raw, actual_winrate_smoothed, avg_pnl_r, avg_mae_r, avg_mfe_r, calibration_offset, sample_size)
        VALUES
            ('very_low', 0.0, 0.40, 0, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0),
            ('low', 0.40, 0.55, 0, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0),
            ('medium', 0.55, 0.70, 0, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0),
            ('high', 0.70, 0.85, 0, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0),
            ('very_high', 0.85, 1.01, 0, 0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0);
    """)


def downgrade() -> None:
    """Drop feedback loop and learning tables."""
    op.drop_table('archetype_stats')
    op.drop_table('confidence_buckets')
    op.drop_table('trade_outcomes')
