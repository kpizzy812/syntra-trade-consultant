"""
Fill Simulator

Симуляция fills для forward testing.
MVP: touch_fill модель (цена коснулась = fill).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from src.services.forward_test.enums import Bias, FillModel
from src.services.forward_test.config import get_config


@dataclass
class SimulatedFill:
    """Результат симуляции fill."""
    order_idx: int
    order_price: float
    size_pct: float
    fill_price: float  # после slippage
    fill_candle_ts: datetime


@dataclass
class EntryOrder:
    """Entry order из сценария."""
    idx: int
    price: float
    size_pct: float


@dataclass
class Candle1m:
    """1-минутная свеча для мониторинга."""
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class FillSimulator:
    """
    Симулятор fills со slippage.

    Модели:
    - touch_fill: цена коснулась order_price = fill
    - prob_fill_by_vol: вероятность fill по объёму (future)
    """

    def __init__(self, fill_model: FillModel = FillModel.TOUCH_FILL):
        self.fill_model = fill_model
        self.config = get_config().slippage

    def check_entry_fill(
        self,
        order: EntryOrder,
        candle: Candle1m,
        bias: Bias
    ) -> Optional[SimulatedFill]:
        """
        Проверить fill для entry order.

        Long: fill если candle.low <= order_price + spread_buffer
        Short: fill если candle.high >= order_price - spread_buffer

        Returns:
            SimulatedFill если fill произошёл, иначе None
        """
        spread_buffer = order.price * (self.config.spread_buffer_bps / 10000)

        touched = False
        if bias == Bias.LONG:
            # Long entry: покупаем, цена должна опуститься до order_price
            touched = candle.low <= order.price + spread_buffer
        else:
            # Short entry: продаём, цена должна подняться до order_price
            touched = candle.high >= order.price - spread_buffer

        if not touched:
            return None

        # Apply slippage
        fill_price = self._apply_entry_slippage(order.price, bias)

        return SimulatedFill(
            order_idx=order.idx,
            order_price=order.price,
            size_pct=order.size_pct,
            fill_price=fill_price,
            fill_candle_ts=candle.ts
        )

    def check_tp_touch(
        self,
        tp_price: float,
        candle: Candle1m,
        bias: Bias
    ) -> bool:
        """
        Проверить касание TP.

        Long: TP hit если candle.high >= tp_price
        Short: TP hit если candle.low <= tp_price
        """
        if bias == Bias.LONG:
            return candle.high >= tp_price
        else:
            return candle.low <= tp_price

    def check_sl_touch(
        self,
        sl_price: float,
        candle: Candle1m,
        bias: Bias
    ) -> bool:
        """
        Проверить касание SL.

        Long: SL hit если candle.low <= sl_price
        Short: SL hit если candle.high >= sl_price
        """
        if bias == Bias.LONG:
            return candle.low <= sl_price
        else:
            return candle.high >= sl_price

    def calculate_weighted_entry(self, fills: List[SimulatedFill]) -> float:
        """
        Рассчитать weighted average entry price.

        Returns:
            Средневзвешенная цена входа
        """
        if not fills:
            return 0.0

        total_weight = sum(f.size_pct for f in fills)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(f.fill_price * f.size_pct for f in fills)
        return weighted_sum / total_weight

    def calculate_fill_pct(self, fills: List[SimulatedFill]) -> float:
        """Рассчитать общий % заполнения."""
        return sum(f.size_pct for f in fills)

    def calculate_exit_price(
        self,
        target_price: float,
        bias: Bias,
        is_tp: bool = True
    ) -> float:
        """
        Рассчитать exit price с учётом slippage.

        TP: slippage в нашу пользу (консервативно не учитываем)
        SL: slippage против нас

        Args:
            target_price: целевая цена выхода
            bias: направление позиции
            is_tp: True если TP, False если SL

        Returns:
            Цена выхода после slippage
        """
        slippage_bps = self.config.exit_bps

        if is_tp:
            # TP: консервативно - без улучшения
            return target_price
        else:
            # SL: slippage против нас
            slippage_pct = slippage_bps / 10000
            if bias == Bias.LONG:
                # Long SL: продаём ниже
                return target_price * (1 - slippage_pct)
            else:
                # Short SL: покупаем выше
                return target_price * (1 + slippage_pct)

    def calculate_r_multiple(
        self,
        entry_price: float,
        exit_price: float,
        initial_risk: float,
        bias: Bias
    ) -> float:
        """
        Рассчитать R-multiple.

        R = direction_sign * (exit - entry) / initial_risk

        Args:
            entry_price: средняя цена входа
            exit_price: цена выхода
            initial_risk: |entry - initial_sl| - FIXED DENOMINATOR
            bias: направление

        Returns:
            R-multiple (может быть отрицательным)
        """
        if initial_risk <= 0:
            return 0.0

        direction = bias.direction_sign()
        pnl = exit_price - entry_price
        return direction * pnl / initial_risk

    def get_mae_price(
        self,
        candle: Candle1m,
        bias: Bias,
        current_mae: Optional[float]
    ) -> Optional[float]:
        """
        Обновить MAE (Max Adverse Excursion) price.

        Long: MAE = min(all lows)
        Short: MAE = max(all highs)
        """
        if bias == Bias.LONG:
            adverse_price = candle.low
            if current_mae is None or adverse_price < current_mae:
                return adverse_price
        else:
            adverse_price = candle.high
            if current_mae is None or adverse_price > current_mae:
                return adverse_price
        return current_mae

    def get_mfe_price(
        self,
        candle: Candle1m,
        bias: Bias,
        current_mfe: Optional[float]
    ) -> Optional[float]:
        """
        Обновить MFE (Max Favorable Excursion) price.

        Long: MFE = max(all highs)
        Short: MFE = min(all lows)
        """
        if bias == Bias.LONG:
            favorable_price = candle.high
            if current_mfe is None or favorable_price > current_mfe:
                return favorable_price
        else:
            favorable_price = candle.low
            if current_mfe is None or favorable_price < current_mfe:
                return favorable_price
        return current_mfe

    def _apply_entry_slippage(self, order_price: float, bias: Bias) -> float:
        """Apply slippage к entry price."""
        slippage_pct = self.config.entry_bps / 10000
        if bias == Bias.LONG:
            # Long: покупаем дороже
            return order_price * (1 + slippage_pct)
        else:
            # Short: продаём дешевле
            return order_price * (1 - slippage_pct)


# Singleton
fill_simulator = FillSimulator()
