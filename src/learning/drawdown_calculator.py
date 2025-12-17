"""
Drawdown Calculator

Расчёт max drawdown по equity curve для Scenario Class Stats.
ВАЖНО: trades должны быть отсортированы по closed_at!
"""
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np


@dataclass
class DrawdownResult:
    """Результат расчёта drawdown."""
    max_drawdown_r: float           # Max DD в R
    max_drawdown_pct: float         # Max DD в % от peak equity
    peak_equity_r: float            # Peak equity в R
    trough_equity_r: float          # Trough equity в R (при max DD)
    peak_index: int                 # Индекс пика
    trough_index: int               # Индекс дна
    recovery_trades: int            # Сделок до recovery (0 если не recovered)
    current_drawdown_r: float       # Текущий DD от последнего пика


def calculate_max_drawdown(pnl_r_series: List[float]) -> DrawdownResult:
    """
    Рассчитать max drawdown по серии PnL.

    ВАЖНО: pnl_r_series должна быть отсортирована по времени закрытия!

    Args:
        pnl_r_series: Список PnL в R (отсортирован по closed_at)

    Returns:
        DrawdownResult с метриками drawdown

    Algorithm:
        1. Строим equity curve: cumsum([0] + pnl_r_series)
        2. Running max (peak) на каждом шаге
        3. Drawdown = peak - equity на каждом шаге
        4. Max DD = max(drawdown)
    """
    if not pnl_r_series:
        return DrawdownResult(
            max_drawdown_r=0.0,
            max_drawdown_pct=0.0,
            peak_equity_r=0.0,
            trough_equity_r=0.0,
            peak_index=0,
            trough_index=0,
            recovery_trades=0,
            current_drawdown_r=0.0,
        )

    # Equity curve начинается с 0
    equity = np.array([0.0] + list(pnl_r_series))
    equity_cumsum = np.cumsum(equity)

    # Running maximum (peak)
    running_max = np.maximum.accumulate(equity_cumsum)

    # Drawdown at each point
    drawdown = running_max - equity_cumsum

    # Max drawdown
    max_dd_idx = np.argmax(drawdown)
    max_dd_r = float(drawdown[max_dd_idx])

    # Find peak index (last index before max_dd_idx where equity == running_max)
    peak_idx = 0
    for i in range(max_dd_idx, -1, -1):
        if equity_cumsum[i] == running_max[max_dd_idx]:
            peak_idx = i
            break

    peak_equity = float(running_max[max_dd_idx])
    trough_equity = float(equity_cumsum[max_dd_idx])

    # Max DD в процентах от пика
    max_dd_pct = (max_dd_r / peak_equity * 100) if peak_equity > 0 else 0.0

    # Recovery trades (сколько сделок до восстановления к пику после дна)
    recovery_trades = 0
    if max_dd_r > 0:
        for i in range(max_dd_idx + 1, len(equity_cumsum)):
            if equity_cumsum[i] >= peak_equity:
                recovery_trades = i - max_dd_idx
                break

    # Current drawdown (от последнего пика)
    current_dd_r = float(running_max[-1] - equity_cumsum[-1])

    return DrawdownResult(
        max_drawdown_r=max_dd_r,
        max_drawdown_pct=max_dd_pct,
        peak_equity_r=peak_equity,
        trough_equity_r=trough_equity,
        peak_index=peak_idx,
        trough_index=max_dd_idx,
        recovery_trades=recovery_trades,
        current_drawdown_r=current_dd_r,
    )


def calculate_drawdown_series(pnl_r_series: List[float]) -> Tuple[List[float], List[float]]:
    """
    Рассчитать серии equity и drawdown для визуализации.

    Args:
        pnl_r_series: Список PnL в R (отсортирован по closed_at)

    Returns:
        (equity_series, drawdown_series) - обе начинаются с 0
    """
    if not pnl_r_series:
        return [0.0], [0.0]

    equity = np.array([0.0] + list(pnl_r_series))
    equity_cumsum = np.cumsum(equity)
    running_max = np.maximum.accumulate(equity_cumsum)
    drawdown = running_max - equity_cumsum

    return equity_cumsum.tolist(), drawdown.tolist()


def calculate_ulcer_index(pnl_r_series: List[float]) -> float:
    """
    Рассчитать Ulcer Index - RMS drawdown.

    Ulcer Index = sqrt(mean(drawdown^2))

    Полезен для оценки "болезненности" equity curve.
    Чем выше - тем более волатильный drawdown.

    Args:
        pnl_r_series: Список PnL в R

    Returns:
        Ulcer Index
    """
    if not pnl_r_series:
        return 0.0

    equity = np.array([0.0] + list(pnl_r_series))
    equity_cumsum = np.cumsum(equity)
    running_max = np.maximum.accumulate(equity_cumsum)

    # Drawdown в процентах от пика
    drawdown_pct = np.where(
        running_max > 0,
        (running_max - equity_cumsum) / running_max * 100,
        0.0
    )

    return float(np.sqrt(np.mean(drawdown_pct ** 2)))


def calculate_calmar_ratio(
    pnl_r_series: List[float],
    annualization_factor: float = 252
) -> float:
    """
    Рассчитать Calmar Ratio = Annualized Return / Max Drawdown.

    Args:
        pnl_r_series: Список PnL в R
        annualization_factor: Множитель для годовой доходности (252 для дневных)

    Returns:
        Calmar Ratio (0 если нет drawdown)
    """
    if not pnl_r_series:
        return 0.0

    dd_result = calculate_max_drawdown(pnl_r_series)

    if dd_result.max_drawdown_r <= 0:
        return float('inf') if sum(pnl_r_series) > 0 else 0.0

    # Средняя доходность за период
    avg_return = np.mean(pnl_r_series)
    # Годовая доходность
    annualized_return = avg_return * annualization_factor

    return annualized_return / dd_result.max_drawdown_r
