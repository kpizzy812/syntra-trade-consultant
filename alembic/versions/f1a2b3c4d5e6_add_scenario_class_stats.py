"""add_scenario_class_stats

Revision ID: f1a2b3c4d5e6
Revises: e76bd21c31a7
Create Date: 2025-12-17

Scenario Class Backtesting System:
- scenario_class_stats: статистика по классам с context gates
- scenario_generation_log: лог генерации для подсчёта conversion
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e76bd21c31a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scenario_class_stats and scenario_generation_log tables."""

    # === SCENARIO CLASS STATS ===
    op.create_table(
        'scenario_class_stats',
        # ID
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # CLASS KEY
        sa.Column('class_key_hash', sa.String(40), nullable=False,
                  comment='SHA1 hash для быстрого lookup'),
        sa.Column('class_key_string', sa.Text(), nullable=False,
                  comment='ARCHETYPE|SIDE|TF|TREND|VOL|FUND|SENT для дебага'),

        # DECOMPOSED KEY (для UNIQUE + CHECK)
        sa.Column('archetype', sa.String(50), nullable=False),
        sa.Column('side', sa.String(10), nullable=False, comment='long/short'),
        sa.Column('timeframe', sa.String(10), nullable=False, comment='1h/4h/1d'),
        sa.Column('trend_bucket', sa.String(20), nullable=False,
                  comment='bullish/bearish/sideways/__any__'),
        sa.Column('vol_bucket', sa.String(20), nullable=False,
                  comment='low/normal/high/__any__'),
        sa.Column('funding_bucket', sa.String(20), nullable=False,
                  comment='strong_negative/negative/neutral/positive/__any__'),
        sa.Column('sentiment_bucket', sa.String(20), nullable=False,
                  comment='fear/neutral/greed/__any__'),

        # PROFITABILITY
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('wins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('losses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('winrate', sa.Float(), nullable=False, server_default='0'),
        sa.Column('winrate_lower_ci', sa.Float(), nullable=False, server_default='0',
                  comment='Wilson score 95% CI lower bound'),
        sa.Column('avg_pnl_r', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_ev_r', sa.Float(), nullable=False, server_default='0',
                  comment='Mean expected value per trade'),
        sa.Column('ev_lower_ci', sa.Float(), nullable=False, server_default='0',
                  comment='EV 95% CI lower bound'),
        sa.Column('profit_factor', sa.Float(), nullable=False, server_default='0',
                  comment='gross_profit / gross_loss'),

        # CONVERSION
        sa.Column('generated_count', sa.Integer(), nullable=False, server_default='0',
                  comment='DISTINCT(analysis_id, scenario_local_id) из log'),
        sa.Column('traded_count', sa.Integer(), nullable=False, server_default='0',
                  comment='DISTINCT(trade_id)'),
        sa.Column('conversion_rate', sa.Float(), nullable=False, server_default='0',
                  comment='traded_count / generated_count'),

        # TERMINAL OUTCOMES
        sa.Column('exit_sl_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('exit_tp1_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('exit_tp2_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('exit_tp3_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('exit_other_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_pnl_r_other', sa.Float(), nullable=False, server_default='0',
                  comment='Средний PnL для OTHER исходов'),

        # RISK
        sa.Column('max_drawdown_r', sa.Float(), nullable=False, server_default='0',
                  comment='Max DD на equity curve'),
        sa.Column('avg_mae_r', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_mfe_r', sa.Float(), nullable=False, server_default='0'),
        sa.Column('p75_mae_r', sa.Float(), nullable=False, server_default='0'),
        sa.Column('p90_mae_r', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_time_in_trade_min', sa.Float(), nullable=False, server_default='0'),

        # EXECUTION
        sa.Column('fill_rate', sa.Float(), nullable=False, server_default='0',
                  comment='opened_trades / selected_trades'),
        sa.Column('avg_slippage_r', sa.Float(), nullable=False, server_default='0'),
        sa.Column('other_exit_rate', sa.Float(), nullable=False, server_default='0'),

        # CONTEXT GATES
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true',
                  comment='False = kill switch активен'),
        sa.Column('disable_reason', sa.Text(), nullable=True,
                  comment='Причина kill switch'),
        sa.Column('preliminary_warning', sa.Text(), nullable=True,
                  comment='Warning для 20-49 trades'),
        sa.Column('confidence_modifier', sa.Float(), nullable=False, server_default='0',
                  comment='+/- к confidence сценария'),
        sa.Column('ev_prior_boost', sa.Float(), nullable=False, server_default='0',
                  comment='Boost для EV prior'),

        # COOLDOWN
        sa.Column('disabled_until', sa.DateTime(timezone=True), nullable=True,
                  comment='Cooldown: держим disabled до этого времени'),
        sa.Column('last_state_change_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Когда последний раз менялся is_enabled'),

        # META
        sa.Column('window_days', sa.Integer(), nullable=False, server_default='90',
                  comment='Rolling window в днях'),
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("(now() at time zone 'utc')")),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("(now() at time zone 'utc')")),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'archetype', 'side', 'timeframe', 'trend_bucket', 'vol_bucket',
            'funding_bucket', 'sentiment_bucket',
            name='uq_scenario_class_key'
        ),
    )

    # Indexes
    op.create_index('ix_class_stats_hash', 'scenario_class_stats', ['class_key_hash'])
    op.create_index('ix_class_stats_archetype', 'scenario_class_stats', ['archetype'])
    op.create_index('ix_class_stats_side', 'scenario_class_stats', ['side'])
    op.create_index('ix_class_stats_timeframe', 'scenario_class_stats', ['timeframe'])

    # CHECK constraints для buckets
    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT check_trend_bucket
        CHECK (trend_bucket IN ('bullish', 'bearish', 'sideways', '__any__'))
    """)
    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT check_vol_bucket
        CHECK (vol_bucket IN ('low', 'normal', 'high', '__any__'))
    """)
    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT check_funding_bucket
        CHECK (funding_bucket IN ('strong_negative', 'negative', 'neutral', 'positive', '__any__'))
    """)
    op.execute("""
        ALTER TABLE scenario_class_stats
        ADD CONSTRAINT check_sentiment_bucket
        CHECK (sentiment_bucket IN ('fear', 'neutral', 'greed', '__any__'))
    """)

    # === SCENARIO GENERATION LOG ===
    op.create_table(
        'scenario_generation_log',
        # ID
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # ИДЕНТИФИКАЦИЯ
        sa.Column('analysis_id', sa.String(50), nullable=False,
                  comment='UUID от Syntra анализа'),
        sa.Column('scenario_local_id', sa.Integer(), nullable=False,
                  comment='1..N в рамках analysis'),

        # CONTEXT
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),

        # CLASS KEY
        sa.Column('class_key_hash', sa.String(40), nullable=False,
                  comment='SHA1 для быстрого lookup в class_stats'),
        sa.Column('archetype', sa.String(50), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),

        # META
        sa.Column('is_testnet', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("(now() at time zone 'utc')"),
                  comment='Для rolling window filter'),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_id', 'scenario_local_id',
                            name='uq_scenario_generation_log'),
    )

    # Indexes
    op.create_index('ix_gen_log_analysis_id', 'scenario_generation_log', ['analysis_id'])
    op.create_index('ix_gen_log_user_id', 'scenario_generation_log', ['user_id'])
    op.create_index('ix_gen_log_symbol', 'scenario_generation_log', ['symbol'])
    op.create_index('ix_gen_log_class_hash', 'scenario_generation_log', ['class_key_hash'])
    op.create_index('ix_gen_log_created', 'scenario_generation_log', ['created_at'])


def downgrade() -> None:
    """Drop tables."""
    # Drop scenario_generation_log
    op.drop_index('ix_gen_log_created', 'scenario_generation_log')
    op.drop_index('ix_gen_log_class_hash', 'scenario_generation_log')
    op.drop_index('ix_gen_log_symbol', 'scenario_generation_log')
    op.drop_index('ix_gen_log_user_id', 'scenario_generation_log')
    op.drop_index('ix_gen_log_analysis_id', 'scenario_generation_log')
    op.drop_table('scenario_generation_log')

    # Drop check constraints
    op.execute('ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS check_sentiment_bucket')
    op.execute('ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS check_funding_bucket')
    op.execute('ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS check_vol_bucket')
    op.execute('ALTER TABLE scenario_class_stats DROP CONSTRAINT IF EXISTS check_trend_bucket')

    # Drop scenario_class_stats
    op.drop_index('ix_class_stats_timeframe', 'scenario_class_stats')
    op.drop_index('ix_class_stats_side', 'scenario_class_stats')
    op.drop_index('ix_class_stats_archetype', 'scenario_class_stats')
    op.drop_index('ix_class_stats_hash', 'scenario_class_stats')
    op.drop_table('scenario_class_stats')
