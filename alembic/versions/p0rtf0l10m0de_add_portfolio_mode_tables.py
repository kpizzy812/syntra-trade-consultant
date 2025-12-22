"""add portfolio mode tables

Revision ID: p0rtf0l10m0de
Revises: vee3pk1pikz8
Create Date: 2025-12-22

Portfolio Mode для Forward Test:
- PortfolioCandidate: кандидаты в портфель
- PortfolioPosition: реальные позиции после fill
- PortfolioEquitySnapshot: equity tracking
- ForwardTestAnomaly: data guardrails
- entry_was_hit field в forward_test_monitor_state
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'p0rtf0l10m0de'
down_revision: Union[str, Sequence[str], None] = 'vee3pk1pikz8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Portfolio Mode tables and fields."""

    # 1. Add entry_was_hit to forward_test_monitor_state (FIX #15)
    op.add_column(
        'forward_test_monitor_state',
        sa.Column(
            'entry_was_hit',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Был ли реальный entry (касание entry zone). Монотонный: False→True only!'
        )
    )

    # 2. Create forward_test_portfolio_candidates table
    op.create_table(
        'forward_test_portfolio_candidates',
        sa.Column('candidate_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('snapshot_id', sa.String(36), nullable=False),
        # Денормализация
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('archetype', sa.String(50), nullable=True),
        # Entry zone
        sa.Column('entry_min', sa.Float(), nullable=False, comment='Min entry price'),
        sa.Column('entry_max', sa.Float(), nullable=False, comment='Max entry price'),
        # Identity
        sa.Column('batch_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, comment='TTL кандидата'),
        # Scoring
        sa.Column('priority_score', sa.Float(), nullable=False, comment='Итоговый score для приоритизации'),
        sa.Column('ev_component', sa.Float(), nullable=False),
        sa.Column('conf_component', sa.Float(), nullable=False),
        sa.Column('quality_component', sa.Float(), nullable=False),
        sa.Column('rank_in_batch', sa.Integer(), nullable=False),
        # Planned allocation
        sa.Column('planned_risk_r', sa.Float(), nullable=False, comment='Планируемый риск в R'),
        # Status
        sa.Column('status', sa.String(30), nullable=False, server_default='active',
                  comment='active/active_waiting_slot/filled/rejected/expired'),
        sa.Column('reject_reason', sa.String(50), nullable=True, comment='Причина отклонения'),
        # Fill attempt tracking
        sa.Column('had_fill_attempt', sa.Boolean(), nullable=False, server_default='false',
                  comment='Был ли реальный fill attempt'),
        sa.Column('fill_attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_fill_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_fill_attempt_price', sa.Float(), nullable=True),
        sa.Column('last_fill_reject_reason', sa.String(50), nullable=True),
        # FIX #25: Два timestamp
        sa.Column('entry_seen_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Когда МЫ увидели entry (observer time)'),
        sa.Column('entry_market_at', sa.DateTime(timezone=True), nullable=True,
                  comment='monitor.entered_at (market time)'),
        # Replacement audit
        sa.Column('replaced_by_candidate_id', sa.Integer(), nullable=True),
        # Link to position
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('position_id', sa.Integer(), nullable=True),
        # Counterfactual
        sa.Column('counterfactual_r_mult_fill_based', sa.Float(), nullable=True),
        sa.Column('counterfactual_r_mult_unconstrained', sa.Float(), nullable=True),
        sa.Column('counterfactual_requires_replacement', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('counterfactual_assumes_entry', sa.Boolean(), nullable=False, server_default='false'),
        # Primary key
        sa.PrimaryKeyConstraint('candidate_id'),
        # Foreign keys
        sa.ForeignKeyConstraint(['snapshot_id'], ['forward_test_snapshots.snapshot_id'], ondelete='CASCADE'),
        # Unique constraint
        sa.UniqueConstraint('snapshot_id', name='uq_candidate_snapshot'),
    )

    # Indexes for forward_test_portfolio_candidates
    op.create_index('ix_candidate_snapshot_id', 'forward_test_portfolio_candidates', ['snapshot_id'])
    op.create_index('ix_candidate_symbol', 'forward_test_portfolio_candidates', ['symbol'])
    op.create_index('ix_candidate_batch_id', 'forward_test_portfolio_candidates', ['batch_id'])
    op.create_index('ix_candidate_status', 'forward_test_portfolio_candidates', ['status'])
    op.create_index('ix_candidate_priority_score', 'forward_test_portfolio_candidates', ['priority_score'])
    op.create_index('ix_candidate_status_expires', 'forward_test_portfolio_candidates', ['status', 'expires_at'])
    op.create_index('ix_candidate_symbol_side_status', 'forward_test_portfolio_candidates', ['symbol', 'side', 'status'])
    op.create_index('ix_candidate_status_score', 'forward_test_portfolio_candidates', ['status', 'priority_score'])

    # FIX #11: Partial unique index для (symbol, side) - active только
    op.execute("""
        CREATE UNIQUE INDEX uq_candidate_active_symbol_side
        ON forward_test_portfolio_candidates (symbol, side)
        WHERE status IN ('active', 'active_waiting_slot')
    """)

    # FIX #22: Partial unique index для max_per_symbol (any side!)
    op.execute("""
        CREATE UNIQUE INDEX uq_candidate_active_symbol
        ON forward_test_portfolio_candidates (symbol)
        WHERE status IN ('active', 'active_waiting_slot')
    """)

    # 3. Create forward_test_portfolio_positions table
    op.create_table(
        'forward_test_portfolio_positions',
        sa.Column('position_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('snapshot_id', sa.String(36), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        # Денормализация
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        # Fill info
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('filled_weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('avg_fill_price', sa.Float(), nullable=False),
        # Allocation snapshot
        sa.Column('equity_at_fill', sa.Float(), nullable=False),
        sa.Column('base_risk_r', sa.Float(), nullable=False),
        sa.Column('risk_r_filled', sa.Float(), nullable=False),
        sa.Column('risk_pct_filled', sa.Float(), nullable=False),
        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        # P&L
        sa.Column('r_mult_realized', sa.Float(), nullable=True),
        sa.Column('pnl_pct_realized', sa.Float(), nullable=True),
        sa.Column('pnl_usd_realized', sa.Float(), nullable=True),
        # Keys
        sa.PrimaryKeyConstraint('position_id'),
        sa.ForeignKeyConstraint(['snapshot_id'], ['forward_test_snapshots.snapshot_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['candidate_id'], ['forward_test_portfolio_candidates.candidate_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('snapshot_id', name='uq_position_snapshot'),
    )

    # Indexes for forward_test_portfolio_positions
    op.create_index('ix_position_snapshot_id', 'forward_test_portfolio_positions', ['snapshot_id'])
    op.create_index('ix_position_symbol', 'forward_test_portfolio_positions', ['symbol'])
    op.create_index('ix_position_status', 'forward_test_portfolio_positions', ['status'])
    op.create_index('ix_position_symbol_side_status', 'forward_test_portfolio_positions', ['symbol', 'side', 'status'])

    # 4. Create forward_test_portfolio_equity table
    op.create_table(
        'forward_test_portfolio_equity',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('trigger', sa.String(30), nullable=False, comment='position_closed / batch_generated'),
        # Current state
        sa.Column('equity_usd', sa.Float(), nullable=False),
        sa.Column('equity_pct_from_initial', sa.Float(), nullable=False),
        sa.Column('open_positions_count', sa.Integer(), nullable=False),
        sa.Column('total_risk_r', sa.Float(), nullable=False),
        sa.Column('active_candidates_count', sa.Integer(), nullable=False),
        sa.Column('risk_utilization_pct', sa.Float(), nullable=False),
        # Peak tracking
        sa.Column('equity_peak_usd', sa.Float(), nullable=False),
        sa.Column('current_drawdown_pct', sa.Float(), nullable=False),
        # Cumulative
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('win_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('loss_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_r_realized', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_drawdown_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes for equity
    op.create_index('ix_equity_ts', 'forward_test_portfolio_equity', ['ts'])

    # 5. Create forward_test_anomalies table (FIX #28)
    op.create_table(
        'forward_test_anomalies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('bug_type', sa.String(50), nullable=False),
        sa.Column('snapshot_id', sa.String(36), nullable=True),
        sa.Column('details', JSONB, nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes for anomalies
    op.create_index('ix_anomaly_ts', 'forward_test_anomalies', ['ts'])
    op.create_index('ix_anomaly_bug_type', 'forward_test_anomalies', ['bug_type'])


def downgrade() -> None:
    """Remove Portfolio Mode tables and fields."""

    # Drop tables in reverse order (due to FK constraints)
    op.drop_table('forward_test_anomalies')
    op.drop_table('forward_test_portfolio_equity')
    op.drop_table('forward_test_portfolio_positions')

    # Drop partial unique indexes first
    op.execute("DROP INDEX IF EXISTS uq_candidate_active_symbol")
    op.execute("DROP INDEX IF EXISTS uq_candidate_active_symbol_side")

    op.drop_table('forward_test_portfolio_candidates')

    # Remove entry_was_hit from monitor_state
    op.drop_column('forward_test_monitor_state', 'entry_was_hit')
