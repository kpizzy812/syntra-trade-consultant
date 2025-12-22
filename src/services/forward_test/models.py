"""
Forward Test Database Models

SQLAlchemy 2.0 models для forward testing системы.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from src.database.models import Base
from src.services.forward_test.enums import (
    ScenarioState,
    TerminalState,
    OutcomeResult,
    PnLClass,
    Bias,
    FillModel,
    EventType,
)


class ForwardTestSnapshot(Base):
    """
    Снимок AI-сценария при генерации для forward testing.

    Хранит RAW LLM response + normalized версию с полным версионированием.
    Retention: 90 дней.
    """
    __tablename__ = "forward_test_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Основной ключ для FK (UUID v4)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        comment="UUID для внешних ссылок"
    )

    # === BATCH INFO ===
    batch_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
        comment="UUID батча генерации"
    )
    batch_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp батча"
    )
    batch_scope: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Scope: 'BTCUSDT:4h:standard'"
    )

    # === UNIVERSE ===
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )
    mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Trading mode: standard/scalping/swing"
    )

    # === SCENARIO IDENTITY ===
    scenario_local_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Локальный ID в batch (1,2,3...)"
    )
    bias: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="LONG/SHORT"
    )
    archetype: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Архетип сценария"
    )

    # === JSON DATA ===
    raw_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="RAW LLM response"
    )
    normalized_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Normalized/validated сценарий"
    )
    market_context_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Market context при генерации"
    )

    # === VERSIONING ===
    version_hash: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="Git commit hash"
    )
    prompt_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Prompt version: v2.1.0"
    )
    schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Schema version number"
    )

    # === KEY PRICES ===
    current_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Цена при генерации"
    )
    entry_price_avg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Средняя цена входа"
    )
    stop_loss: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Stop-loss уровень"
    )
    tp1_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Take-profit 1"
    )
    tp2_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Take-profit 2"
    )
    tp3_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Take-profit 3"
    )

    # === BE LOGIC ===
    be_after_tp1: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Сдвигать SL в BE после TP1"
    )
    be_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="BE цена (обычно = entry_avg)"
    )

    # === CONFIDENCE/EV ===
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Confidence score 0-1"
    )
    ev_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Expected Value в R"
    )

    # === TIMING ===
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Дата истечения сценария"
    )
    time_valid_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
        comment="Срок действия в часах"
    )

    # === INDEXES ===
    __table_args__ = (
        Index('ix_snapshot_gen_sym_tf', 'generated_at', 'symbol', 'timeframe', 'mode'),
        Index('ix_snapshot_batch', 'batch_id', 'batch_ts'),
    )

    def __repr__(self) -> str:
        return (
            f"<ScenarioSnapshot(id={self.snapshot_id[:8]}, "
            f"{self.symbol} {self.bias.value} {self.archetype})>"
        )


class ForwardTestMonitorState(Base):
    """
    Состояние мониторинга сценария для forward testing.

    State machine: armed → triggered → entered → tp1/tp2/tp3/sl/be/expired
    """
    __tablename__ = "forward_test_monitor_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to snapshot
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("forward_test_snapshots.snapshot_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )

    # === STATE MACHINE ===
    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ScenarioState.ARMED.value,
        comment="Текущее состояние"
    )
    state_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # === BIAS (финальный после валидации) ===
    bias_final: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Финальный bias после валидации"
    )
    direction_sign: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="+1 для long, -1 для short"
    )

    # === TRANSITION TIMESTAMPS ===
    triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    entered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    tp1_hit_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="TP1 milestone timestamp"
    )
    exit_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === ENTRY TRACKING (ladder fills) ===
    filled_orders_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="[{order_idx, order_price, size_pct, fill_price, fill_candle_ts}]"
    )
    avg_entry_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Weighted average entry"
    )
    fill_pct: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Процент заполнения 0-100"
    )

    # === SL TRACKING (КРИТИЧНО для R!) ===
    initial_sl: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="SL при входе - FIXED для R calculation"
    )
    initial_risk_per_unit: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="|avg_entry - initial_sl| - DENOMINATOR для R!"
    )
    current_sl: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Текущий SL (меняется после TP1 → BE)"
    )
    sl_moved_to_be: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="SL сдвинут в BE"
    )

    # === FILL MODEL ===
    fill_model: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=FillModel.TOUCH_FILL.value,
        comment="touch_fill | prob_fill_by_vol"
    )

    # === PORTFOLIO MODE (FIX #15) ===
    entry_was_hit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Был ли реальный entry (касание entry zone). Монотонный: False→True only!"
    )

    # === PARTIAL TP TRACKING ===
    tp_progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="0, 1, 2, 3 - количество достигнутых TP"
    )
    realized_r_so_far: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Зафиксированный R от partial TP"
    )
    remaining_position_pct: Mapped[float] = mapped_column(
        Float,
        default=100.0,
        nullable=False,
        comment="Оставшаяся позиция %"
    )

    # === EXIT ===
    exit_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    exit_reason: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="tp2/tp3/sl/be/expired"
    )

    # === MAE/MFE TRACKING ===
    mae_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Max Adverse Excursion price"
    )
    mae_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="MAE в R-multiples"
    )
    mae_candle_ts: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    mfe_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Max Favorable Excursion price"
    )
    mfe_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="MFE в R-multiples"
    )
    mfe_candle_ts: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === TIME ALIGNMENT ===
    last_checked_candle_ts: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp последней проверенной свечи"
    )
    candle_source: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="bybit | binance"
    )
    candle_lag_sec: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Лаг свечей в секундах (алерт если > 180)"
    )

    # === INDEXES ===
    __table_args__ = (
        Index('ix_monitor_state_updated', 'state', 'state_updated_at'),
        Index('ix_monitor_active', 'state',
              postgresql_where="state IN ('armed', 'triggered', 'entered', 'tp1')"),
    )

    def __repr__(self) -> str:
        return (
            f"<ScenarioMonitorState(snapshot={self.snapshot_id[:8]}, "
            f"state={self.state}, fill={self.fill_pct}%)>"
        )


class ForwardTestEvent(Base):
    """
    Лог событий сценария для forward testing.

    Каждое изменение состояния записывается как event.
    Retention: 30 дней (trace_json в outcome сохраняет ключевые timestamps).
    """
    __tablename__ = "forward_test_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to snapshot
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("forward_test_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # === EVENT DATA ===
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Timestamp события"
    )
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Тип события"
    )
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Цена при событии"
    )
    details_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Детали: {partial_close_pct, realized_r, ...}"
    )

    # === INDEXES ===
    __table_args__ = (
        Index('ix_event_snapshot_ts', 'snapshot_id', 'ts'),
    )

    def __repr__(self) -> str:
        return (
            f"<ScenarioEvent(snapshot={self.snapshot_id[:8]}, "
            f"type={self.event_type}, price={self.price})>"
        )


class ForwardTestOutcome(Base):
    """
    Результат forward test (paper trade).

    Создаётся при достижении terminal state.
    Retention: 180 дней (для сравнения версий).
    """
    __tablename__ = "forward_test_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to snapshot (unique - один outcome на snapshot)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("forward_test_snapshots.snapshot_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )

    # === RESULT ===
    result: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="win/loss/breakeven/expired"
    )
    terminal_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="tp2/tp3/sl/be/expired (НЕ tp1!)"
    )

    # === CLARITY FIELDS ===
    is_profit: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="total_r > 0"
    )
    pnl_class: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="win/loss/flat для фильтрации"
    )

    # === R CALCULATION ===
    realized_r_from_tp1: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="R от partial TP1"
    )
    remaining_r: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="R от остатка позиции"
    )
    total_r: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="realized_r_from_tp1 + remaining_r"
    )
    fill_pct_at_exit: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Процент заполнения при выходе"
    )

    # === MAE/MFE ===
    mae_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Max Adverse Excursion в R"
    )
    mfe_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Max Favorable Excursion в R"
    )

    # === TIMING ===
    time_to_trigger_sec: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Время до trigger в секундах"
    )
    time_to_entry_sec: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Время до entry в секундах"
    )
    time_to_exit_sec: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Время до exit в секундах"
    )
    hold_time_sec: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Время в позиции в секундах"
    )

    # === FILL MODEL ===
    fill_model: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=FillModel.TOUCH_FILL.value
    )

    # === ADJUSTMENTS ===
    slippage_bps: Mapped[float] = mapped_column(
        Float,
        default=3.0,
        nullable=False,
        comment="Slippage в basis points"
    )
    fees_bps: Mapped[float] = mapped_column(
        Float,
        default=2.0,
        nullable=False,
        comment="Fees в basis points"
    )

    # === NOTES ===
    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # === TRACE FOR DEBUGGING ===
    trace_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Trace для debugging когда events удалены"
    )

    # === TIMESTAMPS ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # === INDEXES ===
    __table_args__ = (
        Index('ix_outcome_created_result', 'created_at', 'result'),
        Index('ix_outcome_pnl_class', 'pnl_class'),
        Index('ix_outcome_total_r', 'total_r'),
    )

    def __repr__(self) -> str:
        return (
            f"<PaperTradeOutcome(snapshot={self.snapshot_id[:8]}, "
            f"result={self.result}, total_r={self.total_r:.2f}R)>"
        )


# =============================================================================
# PORTFOLIO MODE MODELS
# =============================================================================


class PortfolioCandidate(Base):
    """
    Кандидат в портфель. Ждёт исполнения entry.

    Lifecycle: active → active_waiting_slot → filled/rejected/expired
    """
    __tablename__ = "forward_test_portfolio_candidates"

    candidate_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # FK to snapshot (unique - один candidate на snapshot)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("forward_test_snapshots.snapshot_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )

    # === ДЕНОРМАЛИЗАЦИЯ (для быстрых фильтров без join) ===
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    archetype: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # === ENTRY ZONE (для анализа "почему не вошли") ===
    entry_min: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Min entry price"
    )
    entry_max: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Max entry price"
    )

    # === IDENTITY ===
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="TTL кандидата"
    )

    # === SCORING ===
    priority_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
        comment="Итоговый score для приоритизации"
    )
    ev_component: Mapped[float] = mapped_column(Float, nullable=False)
    conf_component: Mapped[float] = mapped_column(Float, nullable=False)
    quality_component: Mapped[float] = mapped_column(Float, nullable=False)
    rank_in_batch: Mapped[int] = mapped_column(Integer, nullable=False)

    # === PLANNED ALLOCATION ===
    planned_risk_r: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Планируемый риск в R (= base_risk при создании)"
    )

    # === STATUS ===
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        index=True,
        comment="active/active_waiting_slot/filled/rejected/expired"
    )
    reject_reason: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Причина отклонения"
    )

    # === FILL ATTEMPT TRACKING ===
    had_fill_attempt: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Был ли реальный fill attempt (entry случился)"
    )
    fill_attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Счётчик попыток (инкремент при смене reject reason)"
    )
    last_fill_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_fill_attempt_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    last_fill_reject_reason: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="fill_no_slot / fill_no_risk_budget"
    )

    # === FIX #25: ДВА TIMESTAMP ДЛЯ ENTRY ===
    entry_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда МЫ увидели entry (observer time)"
    )
    entry_market_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="monitor.entered_at (market time)"
    )

    # === REPLACEMENT AUDIT ===
    replaced_by_candidate_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="ID кандидата, который вытеснил"
    )

    # === LINK TO POSITION (after fill) ===
    filled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    position_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="FK to PortfolioPosition (после fill)"
    )

    # === COUNTERFACTUAL (FIX #18+#27) ===
    counterfactual_r_mult_fill_based: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="R если бы взяли (entry был)"
    )
    counterfactual_r_mult_unconstrained: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="R без ограничений портфеля"
    )
    counterfactual_requires_replacement: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="FIX #18: pool_full/replaced_by_better"
    )
    counterfactual_assumes_entry: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="FIX #27: True если entry реально был"
    )

    # === INDEXES ===
    __table_args__ = (
        Index("ix_candidate_status_expires", "status", "expires_at"),
        Index("ix_candidate_symbol_side_status", "symbol", "side", "status"),
        Index("ix_candidate_status_score", "status", "priority_score"),
        # FIX #11: Partial unique index для (symbol, side)
        Index(
            "uq_candidate_active_symbol_side",
            "symbol", "side",
            unique=True,
            postgresql_where=text("status IN ('active', 'active_waiting_slot')")
        ),
        # FIX #22: Partial unique index для max_per_symbol (any side!)
        Index(
            "uq_candidate_active_symbol",
            "symbol",
            unique=True,
            postgresql_where=text("status IN ('active', 'active_waiting_slot')")
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioCandidate(id={self.candidate_id}, "
            f"{self.symbol} {self.side}, status={self.status}, "
            f"score={self.priority_score:.2f})>"
        )


class PortfolioPosition(Base):
    """
    Позиция в портфеле. Создаётся только при fill.

    Lifecycle: open → closed
    """
    __tablename__ = "forward_test_portfolio_positions"

    position_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # FK to snapshot (unique - одна position на snapshot)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("forward_test_snapshots.snapshot_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("forward_test_portfolio_candidates.candidate_id", ondelete="CASCADE"),
        nullable=False
    )

    # === ДЕНОРМАЛИЗАЦИЯ (для anti-dup без join) ===
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)

    # === FILL INFO ===
    filled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    filled_weight: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="0.0-1.0 (MVP: всегда 1.0)"
    )
    avg_fill_price: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    # === ALLOCATION SNAPSHOT AT FILL TIME ===
    equity_at_fill: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Equity на момент fill"
    )
    base_risk_r: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="max_total_risk / max_positions"
    )
    risk_r_filled: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="base_risk * filled_weight"
    )
    risk_pct_filled: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="risk_r_filled * r_to_pct"
    )

    # === LADDER TP TRACKING (v8) ===
    remaining_pct: Mapped[float] = mapped_column(
        Float,
        default=100.0,
        nullable=False,
        comment="Remaining position after partial closes (100 -> 70 after TP1)"
    )
    risk_r_current: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Current risk = risk_r_filled * remaining_pct / 100"
    )
    tp_progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="0,1,2,3 - synced from monitor.tp_progress"
    )

    # === UNREALIZED R TRACKING ===
    realized_r_so_far: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Synced from monitor.realized_r_so_far"
    )

    # === MFE/MAE DENORMALIZED ===
    mfe_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Max Favorable Excursion (synced from monitor)"
    )
    mae_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Max Adverse Excursion (synced from monitor)"
    )

    # === STATUS ===
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
        index=True,
        comment="open/closed"
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === P&L ===
    r_mult_realized: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="R-multiple результата"
    )
    pnl_pct_realized: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="r_mult * risk_pct_filled"
    )
    pnl_usd_realized: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="equity_at_fill * pnl_pct"
    )

    # === INDEXES ===
    __table_args__ = (
        Index("ix_position_status", "status"),
        Index("ix_position_symbol_side_status", "symbol", "side", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioPosition(id={self.position_id}, "
            f"{self.symbol} {self.side}, status={self.status}, "
            f"risk={self.risk_r_filled:.2f}R)>"
        )


class PortfolioEquitySnapshot(Base):
    """
    Снимок equity портфеля для tracking.

    Создаётся при: position_closed, batch_generated
    """
    __tablename__ = "forward_test_portfolio_equity"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    trigger: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="position_closed / batch_generated"
    )

    # === CURRENT STATE ===
    equity_usd: Mapped[float] = mapped_column(Float, nullable=False)
    equity_pct_from_initial: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="(equity / initial - 1) * 100"
    )
    open_positions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_risk_r: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Сумма risk_r_filled всех open позиций"
    )
    active_candidates_count: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_utilization_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="total_risk / max_total_risk"
    )

    # === PEAK TRACKING ===
    equity_peak_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="High-water mark"
    )
    current_drawdown_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="(peak - current) / peak"
    )

    # === CUMULATIVE ===
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_r_realized: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Weighted sum: r_mult * risk_r_filled"
    )
    max_drawdown_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Исторический max DD"
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioEquitySnapshot(ts={self.ts}, "
            f"equity=${self.equity_usd:.2f}, DD={self.current_drawdown_pct:.1f}%)>"
        )


class ForwardTestAnomaly(Base):
    """
    Аномалии/баги для алертов (FIX #28).

    Персистентные счётчики вместо in-memory.
    """
    __tablename__ = "forward_test_anomalies"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    bug_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="sl_be_without_entry / outcome_without_terminal / etc"
    )
    snapshot_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True
    )

    def __repr__(self) -> str:
        return f"<ForwardTestAnomaly(type={self.bug_type}, ts={self.ts})>"
