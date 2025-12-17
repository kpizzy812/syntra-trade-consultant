"""add_scenario_class_stats

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-12-17

Scenario Class Backtesting System:
- scenario_class_stats: статистика по классам сценариев с context gates
- scenario_generation_log: трекинг сгенерированных сценариев для conversion rate

Classes: archetype + side + timeframe + [trend_bucket + vol_bucket + funding_bucket + sentiment_bucket]
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scenario_class_stats and scenario_generation_log tables."""

    # === SCENARIO CLASS STATS ===
    op.create_table(
        'scenario_class_stats',
        # PK
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),

        # === CLASS KEY (для быстрого lookup) ===
        sa.Column('class_key_hash', sa.String(40), nullable=False, index=True,
                  comment='SHA1 hash для быстрого lookup'),
        sa.Column('class_key_string', sa.Text(), nullable=False,
                  comment='ARCHETYPE|SIDE|TF|TREND|VOL|FUND|SENT для дебага'),

        # === DECOMPOSED KEY (для UNIQUE + CHECK) ===
        sa.Column('archetype', sa.String(50), nullable=False, index=True),
        sa.Column('side', sa.String(10), nullable=False, index=True,
                  comment='long/short'),
        sa.Column('timeframe', sa.String(10), nullable=False, index=True,
                  comment='1h/4h/1d'),
        sa.Column('trend_bucket', sa.String(20), nullable=False,
                  comment='bullish/bearish/sideways/__any__'),
        sa.Column('vol_bucket', sa.String(20), nullable=False,
                  comment='low/normal/high/__any__'),
        sa.Column('funding_bucket', sa.String(20), nullable=False,
                  comment='strong_negative/negative/neutral/positive/__any__'),
        sa.Column('sentiment_bucket', sa.String(20), nullable=False,
                  comment='fear/neutral/greed/__any__'),

        # === PROFITABILITY ===
        sa.Column('total_trades', sa.Integer(), nullable=False, default=0,
                  comment='= traded_count'),
        sa.Column('wins', sa.Integer(), nullable=False, default=0),
        sa.Column('losses', sa.Integer(), nullable=False, default=0),
        sa.Column('winrate', sa.Float(), nullable=False, default=0),
        sa.Column('winrate_lower_ci', sa.Float(), nullable=False, default=0,
                  comment='Wilson score 95% CI lower bound'),
        sa.Column('avg_pnl_r', sa.Float(), nullable=False, default=0),
        sa.Column('avg_ev_r', sa.Float(), nullable=False, default=0,
                  comment='Mean expected value per trade'),
        sa.Column('ev_lower_ci', sa.Float(), nullable=False, default=0,
                  comment='EV 95% CI lower bound'),
        sa.Column('profit_factor', sa.Float(), nullable=False, default=0,
                  comment='gross_profit / gross_loss'),

        # === CONVERSION ===
        sa.Column('generated_count', sa.Integer(), nullable=False, default=0,
                  comment='DISTINCT(analysis_id, scenario_local_id) из log'),
        sa.Column('traded_count', sa.Integer(), nullable=False, default=0,
                  comment='DISTINCT(trade_id)'),
        sa.Column('conversion_rate', sa.Float(), nullable=False, default=0,
                  comment='traded_count / generated_count'),

        # === TERMINAL OUTCOMES ===
        sa.Column('exit_sl_count', sa.Integer(), nullable=False, default=0),
        sa.Column('exit_tp1_count', sa.Integer(), nullable=False, default=0),
        sa.Column('exit_tp2_count', sa.Integer(), nullable=False, default=0),
        sa.Column('exit_tp3_count', sa.Integer(), nullable=False, default=0),
        sa.Column('exit_other_count', sa.Integer(), nullable=False, default=0),
        sa.Column('avg_pnl_r_other', sa.Float(), nullable=False, default=0,
                  comment='Средний PnL для OTHER исходов'),

        # === RISK ===
        sa.Column('max_drawdown_r', sa.Float(), nullable=False, default=0,
                  comment='Max DD на equity curve (sorted by closed_at!)'),
        sa.Column('avg_mae_r', sa.Float(), nullable=False, default=0),
        sa.Column('avg_mfe_r', sa.Float(), nullable=False, default=0),
        sa.Column('p75_mae_r', sa.Float(), nullable=False, default=0),
        sa.Column('p90_mae_r', sa.Float(), nullable=False, default=0),
        sa.Column('avg_time_in_trade_min', sa.Float(), nullable=False, default=0),

        # === EXECUTION ===
        sa.Column('fill_rate', sa.Float(), nullable=False, default=0,
                  comment='opened_trades / selected_trades'),
        sa.Column('avg_slippage_r', sa.Float(), nullable=False, default=0),
        sa.Column('other_exit_rate', sa.Float(), nullable=False, default=0),

        # === CONTEXT GATES ===
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True,
                  comment='False = kill switch активен'),
        sa.Column('disable_reason', sa.Text(), nullable=True,
                  comment='Причина kill switch'),
        sa.Column('preliminary_warning', sa.Text(), nullable=True,
                  comment='Warning для 20-49 trades'),
        sa.Column('confidence_modifier', sa.Float(), nullable=False, default=0,
                  comment='+/- к confidence сценария'),
        sa.Column('ev_prior_boost', sa.Float(), nullable=False, default=0,
                  comment='Boost для EV prior'),

        # === COOLDOWN ===
        sa.Column('disabled_until', sa.DateTime(timezone=True), nullable=True,
                  comment='Cooldown: держим disabled до этого времени'),
        sa.Column('last_state_change_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Когда последний раз менялся is_enabled'),

        # === META ===
        sa.Column('window_days', sa.Integer(), nullable=False, default=90,
                  comment='Rolling window в днях'),
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )

    # === UNIQUE CONSTRAINT ===
    op.create_unique_constraint(
        'uq_scenario_class_key',
        'scenario_class_stats',
        ['archetype', 'side', 'timeframe', 'trend_bucket', 'vol_bucket',
         'funding_bucket', 'sentiment_bucket']
    )

    # === CHECK CONSTRAINTS для bucket values ===
    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT chk_trend_bucket
        CHECK (trend_bucket IN ('bullish', 'bearish', 'sideways', '__any__'))
    """)

    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT chk_vol_bucket
        CHECK (vol_bucket IN ('low', 'normal', 'high', '__any__'))
    """)

    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT chk_funding_bucket
        CHECK (funding_bucket IN ('strong_negative', 'negative', 'neutral', 'positive', '__any__'))
    """)

    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT chk_sentiment_bucket
        CHECK (sentiment_bucket IN ('fear', 'neutral', 'greed', '__any__'))
    """)

    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT chk_side
        CHECK (side IN ('long', 'short'))
    """)

    # === SCENARIO GENERATION LOG ===
    op.create_table(
        'scenario_generation_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),

        # === ИДЕНТИФИКАЦИЯ ===
        sa.Column('analysis_id', sa.String(50), nullable=False, index=True,
                  comment='UUID от Syntra анализа'),
        sa.Column('scenario_local_id', sa.Integer(), nullable=False,
                  comment='1..N в рамках analysis'),

        # === CONTEXT ===
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timeframe', sa.String(10), nullable=False),

        # === CLASS KEY ===
        sa.Column('class_key_hash', sa.String(40), nullable=False, index=True,
                  comment='SHA1 для быстрого lookup в class_stats'),
        sa.Column('archetype', sa.String(50), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),

        # === META ===
        sa.Column('is_testnet', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  index=True, comment='Для rolling window filter'),
    )

    # === UNIQUE: один сценарий = одна запись (идемпотентность) ===
    op.create_unique_constraint(
        'uq_scenario_generation',
        'scenario_generation_log',
        ['analysis_id', 'scenario_local_id']
    )

    # === COMPOSITE INDEX для recalculate query ===
    op.create_index(
        'ix_gen_log_class_hash_created',
        'scenario_generation_log',
        ['class_key_hash', 'created_at']
    )


def downgrade() -> None:
    """Drop scenario_class_stats and scenario_generation_log tables."""

    # Drop scenario_generation_log
    op.drop_index('ix_gen_log_class_hash_created', table_name='scenario_generation_log')
    op.drop_constraint('uq_scenario_generation', 'scenario_generation_log', type_='unique')
    op.drop_table('scenario_generation_log')

    # Drop scenario_class_stats
    op.execute("ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS chk_side")
    op.execute("ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS chk_sentiment_bucket")
    op.execute("ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS chk_funding_bucket")
    op.execute("ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS chk_vol_bucket")
    op.execute("ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS chk_trend_bucket")
    op.drop_constraint('uq_scenario_class_key', 'scenario_class_stats', type_='unique')
    op.drop_table('scenario_class_stats')
