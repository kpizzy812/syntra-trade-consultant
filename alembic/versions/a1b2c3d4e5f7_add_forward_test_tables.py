"""add_forward_test_tables

Revision ID: a1b2c3d4e5f7
Revises: vee3pk1pikz8
Create Date: 2025-12-19 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'vee3pk1pikz8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create forward test tables."""

    # Create ENUMs using raw SQL with IF NOT EXISTS
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scenario_state_enum') THEN
                CREATE TYPE scenario_state_enum AS ENUM (
                    'armed', 'triggered', 'entered', 'tp1', 'tp2', 'tp3',
                    'sl', 'be', 'expired', 'invalid'
                );
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'terminal_state_enum') THEN
                CREATE TYPE terminal_state_enum AS ENUM ('tp2', 'tp3', 'sl', 'be', 'expired');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'outcome_result_enum') THEN
                CREATE TYPE outcome_result_enum AS ENUM ('win', 'loss', 'breakeven', 'expired');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pnl_class_enum') THEN
                CREATE TYPE pnl_class_enum AS ENUM ('win', 'loss', 'flat');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bias_enum') THEN
                CREATE TYPE bias_enum AS ENUM ('long', 'short');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fill_model_enum') THEN
                CREATE TYPE fill_model_enum AS ENUM ('touch_fill', 'prob_fill_by_vol');
            END IF;
        END$$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'event_type_enum') THEN
                CREATE TYPE event_type_enum AS ENUM (
                    'trigger_hit', 'entry_fill', 'tp1_hit', 'tp2_hit', 'tp3_hit',
                    'sl_hit', 'be_hit', 'expired', 'be_moved'
                );
            END IF;
        END$$;
    """)

    # 1. forward_test_snapshots
    op.create_table(
        'forward_test_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('snapshot_id', sa.String(36), nullable=False, comment='UUID для внешних ссылок'),
        sa.Column('batch_id', sa.String(36), nullable=False, comment='UUID батча генерации'),
        sa.Column('batch_ts', sa.DateTime(timezone=True), nullable=False, comment='Timestamp батча'),
        sa.Column('batch_scope', sa.String(100), nullable=False, comment='Scope: BTCUSDT:4h:standard'),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False, comment='Trading mode'),
        sa.Column('scenario_local_id', sa.Integer(), nullable=False, comment='Локальный ID в batch'),
        sa.Column('bias', sa.String(10), nullable=False, comment='long/short'),
        sa.Column('archetype', sa.String(50), nullable=False),
        sa.Column('raw_json', postgresql.JSONB(), nullable=False, comment='RAW LLM response'),
        sa.Column('normalized_json', postgresql.JSONB(), nullable=False, comment='Normalized сценарий'),
        sa.Column('market_context_json', postgresql.JSONB(), nullable=True),
        sa.Column('version_hash', sa.String(40), nullable=False, comment='Git commit hash'),
        sa.Column('prompt_version', sa.String(20), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('current_price', sa.Float(), nullable=False),
        sa.Column('entry_price_avg', sa.Float(), nullable=False),
        sa.Column('stop_loss', sa.Float(), nullable=False),
        sa.Column('tp1_price', sa.Float(), nullable=False),
        sa.Column('tp2_price', sa.Float(), nullable=True),
        sa.Column('tp3_price', sa.Float(), nullable=True),
        sa.Column('be_after_tp1', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('be_price', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('ev_r', sa.Float(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_valid_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ft_snapshots_snapshot_id', 'forward_test_snapshots', ['snapshot_id'], unique=True)
    op.create_index('ix_ft_snapshots_batch_id', 'forward_test_snapshots', ['batch_id'], unique=False)
    op.create_index('ix_ft_snapshots_symbol', 'forward_test_snapshots', ['symbol'], unique=False)
    op.create_index('ix_ft_snapshots_archetype', 'forward_test_snapshots', ['archetype'], unique=False)
    op.create_index('ix_ft_snapshots_generated_at', 'forward_test_snapshots', ['generated_at'], unique=False)
    op.create_index('ix_ft_snapshots_gen_sym_tf', 'forward_test_snapshots',
                    ['generated_at', 'symbol', 'timeframe', 'mode'], unique=False)

    # 2. forward_test_monitor_state
    op.create_table(
        'forward_test_monitor_state',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('snapshot_id', sa.String(36), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, comment='armed|triggered|entered|tp1|tp2|tp3|sl|be|expired|invalid'),
        sa.Column('state_updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('bias_final', sa.String(10), nullable=False, comment='long/short'),
        sa.Column('direction_sign', sa.Integer(), nullable=False, comment='+1 long, -1 short'),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('entered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tp1_hit_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('exit_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('filled_orders_json', postgresql.JSONB(), nullable=True),
        sa.Column('avg_entry_price', sa.Float(), nullable=True),
        sa.Column('fill_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('initial_sl', sa.Float(), nullable=True, comment='SL при входе - FIXED для R'),
        sa.Column('initial_risk_per_unit', sa.Float(), nullable=True, comment='DENOMINATOR для R'),
        sa.Column('current_sl', sa.Float(), nullable=True),
        sa.Column('sl_moved_to_be', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('fill_model', sa.String(20), nullable=False, server_default='touch_fill'),
        sa.Column('tp_progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('realized_r_so_far', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('remaining_position_pct', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('exit_reason', sa.String(50), nullable=True),
        sa.Column('mae_price', sa.Float(), nullable=True),
        sa.Column('mae_r', sa.Float(), nullable=True),
        sa.Column('mae_candle_ts', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mfe_price', sa.Float(), nullable=True),
        sa.Column('mfe_r', sa.Float(), nullable=True),
        sa.Column('mfe_candle_ts', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_checked_candle_ts', sa.DateTime(timezone=True), nullable=True),
        sa.Column('candle_source', sa.String(20), nullable=True),
        sa.Column('candle_lag_sec', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['snapshot_id'], ['forward_test_snapshots.snapshot_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ft_monitor_snapshot_id', 'forward_test_monitor_state', ['snapshot_id'], unique=True)
    op.create_index('ix_ft_monitor_state_updated', 'forward_test_monitor_state', ['state', 'state_updated_at'], unique=False)

    # 3. forward_test_events
    op.create_table(
        'forward_test_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('snapshot_id', sa.String(36), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(20), nullable=False, comment='trigger_hit|entry_fill|tp1_hit|...'),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('details_json', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['snapshot_id'], ['forward_test_snapshots.snapshot_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ft_events_snapshot_id', 'forward_test_events', ['snapshot_id'], unique=False)
    op.create_index('ix_ft_events_ts', 'forward_test_events', ['ts'], unique=False)
    op.create_index('ix_ft_events_snapshot_ts', 'forward_test_events', ['snapshot_id', 'ts'], unique=False)

    # 4. forward_test_outcomes
    op.create_table(
        'forward_test_outcomes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('snapshot_id', sa.String(36), nullable=False),
        sa.Column('result', sa.String(20), nullable=False, comment='win|loss|breakeven|expired'),
        sa.Column('terminal_state', sa.String(20), nullable=False, comment='tp2|tp3|sl|be|expired'),
        sa.Column('is_profit', sa.Boolean(), nullable=False),
        sa.Column('pnl_class', sa.String(10), nullable=False, comment='win|loss|flat'),
        sa.Column('realized_r_from_tp1', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('remaining_r', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_r', sa.Float(), nullable=False),
        sa.Column('fill_pct_at_exit', sa.Float(), nullable=False),
        sa.Column('mae_r', sa.Float(), nullable=True),
        sa.Column('mfe_r', sa.Float(), nullable=True),
        sa.Column('time_to_trigger_sec', sa.Integer(), nullable=True),
        sa.Column('time_to_entry_sec', sa.Integer(), nullable=True),
        sa.Column('time_to_exit_sec', sa.Integer(), nullable=True),
        sa.Column('hold_time_sec', sa.Integer(), nullable=True),
        sa.Column('fill_model', sa.String(20), nullable=False, server_default='touch_fill'),
        sa.Column('slippage_bps', sa.Float(), nullable=False, server_default='3.0'),
        sa.Column('fees_bps', sa.Float(), nullable=False, server_default='2.0'),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('trace_json', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['snapshot_id'], ['forward_test_snapshots.snapshot_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ft_outcomes_snapshot_id', 'forward_test_outcomes', ['snapshot_id'], unique=True)
    op.create_index('ix_ft_outcomes_created_at', 'forward_test_outcomes', ['created_at'], unique=False)
    op.create_index('ix_ft_outcomes_created_result', 'forward_test_outcomes', ['created_at', 'result'], unique=False)
    op.create_index('ix_ft_outcomes_pnl_class', 'forward_test_outcomes', ['pnl_class'], unique=False)
    op.create_index('ix_ft_outcomes_total_r', 'forward_test_outcomes', ['total_r'], unique=False)


def downgrade() -> None:
    """Drop forward test tables."""
    # Drop tables in reverse order (due to FK constraints)
    op.drop_table('forward_test_outcomes')
    op.drop_table('forward_test_events')
    op.drop_table('forward_test_monitor_state')
    op.drop_table('forward_test_snapshots')

    # Drop ENUMs (only if not used by other tables)
    op.execute('DROP TYPE IF EXISTS event_type_enum')
    op.execute('DROP TYPE IF EXISTS fill_model_enum')
    op.execute('DROP TYPE IF EXISTS bias_enum')
    op.execute('DROP TYPE IF EXISTS pnl_class_enum')
    op.execute('DROP TYPE IF EXISTS outcome_result_enum')
    op.execute('DROP TYPE IF EXISTS terminal_state_enum')
    op.execute('DROP TYPE IF EXISTS scenario_state_enum')
