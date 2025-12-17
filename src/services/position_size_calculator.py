# coding: utf-8
"""
Position Size Calculator

Рассчитывает размер позиции на основе пользовательского риска и баланса
с точным округлением до qtyStep биржи.

КРИТИЧНО для quick-execute интеграции с трейдинг-ботом!
"""
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP
from dataclasses import dataclass

from loguru import logger


@dataclass
class InstrumentInfo:
    """Информация об инструменте с биржи"""
    symbol: str
    qty_step: str
    tick_size: str
    min_order_qty: str
    max_order_qty: str
    min_notional: str
    max_leverage: int


@dataclass
class PositionParams:
    """Параметры позиции для расчёта"""
    symbol: str
    side: str  # "long" | "short"
    entry_price: float
    stop_loss: float
    risk_usd: float
    leverage: int
    account_balance: Optional[float] = None
    max_margin: Optional[float] = None
    max_risk: Optional[float] = None


class PositionSizeCalculator:
    """
    Калькулятор размера позиции с точным округлением

    Формулы:
    1. qty_raw = risk_usd / stop_distance
    2. qty_rounded = round_to_qty_step(qty_raw)
    3. margin_required = (qty * entry_price) / leverage
    4. actual_risk = qty_rounded * stop_distance

    ВАЖНО: Используем Decimal для точного округления без артефактов float!
    """

    def __init__(self):
        logger.info("PositionSizeCalculator initialized")

    def calculate(
        self,
        params: PositionParams,
        instrument: InstrumentInfo
    ) -> Dict[str, Any]:
        """
        Рассчитать размер позиции

        Args:
            params: Параметры позиции (entry, SL, risk, leverage)
            instrument: Информация об инструменте (qtyStep, etc.)

        Returns:
            Dict с расчётами позиции и валидацией
        """
        try:
            # 1. РАСЧЁТ БАЗОВЫХ ПАРАМЕТРОВ
            stop_distance = abs(params.entry_price - params.stop_loss)

            if stop_distance == 0:
                return {
                    "success": False,
                    "error": "Stop loss cannot equal entry price"
                }

            # 2. РАСЧЁТ СЫРОГО КОЛИЧЕСТВА
            qty_raw = params.risk_usd / stop_distance

            logger.debug(
                f"Position calculation: "
                f"risk=${params.risk_usd}, "
                f"stop_distance={stop_distance:.4f}, "
                f"qty_raw={qty_raw:.8f}"
            )

            # 3. ОКРУГЛЕНИЕ ДО QTY_STEP (с Decimal!)
            qty_rounded, qty_str = self._round_qty(qty_raw, instrument.qty_step)

            # 4. РАСЧЁТ ФАКТИЧЕСКОГО РИСКА (после округления)
            actual_risk_usd = float(qty_rounded) * stop_distance

            # 5. РАСЧЁТ MARGIN REQUIRED
            margin_required = (float(qty_rounded) * params.entry_price) / params.leverage

            # 6. РАСЧЁТ NOTIONAL
            notional = float(qty_rounded) * params.entry_price

            # 7. РАСЧЁТ RR (если есть target)
            stop_distance_pct = (stop_distance / params.entry_price) * 100

            # 8. ОЦЕНКА ЛИКВИДАЦИИ (упрощённая формула)
            liq_price_estimate = self._estimate_liquidation_price(
                entry_price=params.entry_price,
                leverage=params.leverage,
                side=params.side
            )

            # 9. ВАЛИДАЦИЯ
            validation = self._validate_position(
                qty=qty_rounded,
                notional=notional,
                margin_required=margin_required,
                actual_risk_usd=actual_risk_usd,
                params=params,
                instrument=instrument
            )

            # 10. РЕЗУЛЬТАТ
            result = {
                "success": True,
                "position": {
                    "symbol": params.symbol,
                    "side": params.side,

                    # Entry
                    "entry_price": round(params.entry_price, 2),
                    "entry_type": "market",

                    # Position sizing
                    "qty": qty_str,
                    "qty_raw": qty_raw,

                    # Risk/Margin
                    "risk_usd": params.risk_usd,
                    "actual_risk_usd": round(actual_risk_usd, 2),
                    "margin_required": round(margin_required, 2),

                    # Stop/TP
                    "stop_loss": round(params.stop_loss, 2),

                    # Leverage
                    "leverage": params.leverage,

                    # Risk metrics
                    "stop_distance_percent": round(stop_distance_pct, 2),
                    "notional": round(notional, 2),

                    # Instrument info
                    "instrument_info": {
                        "qty_step": instrument.qty_step,
                        "tick_size": instrument.tick_size,
                        "min_order_qty": instrument.min_order_qty,
                        "max_order_qty": instrument.max_order_qty,
                        "min_notional": instrument.min_notional,
                    }
                },

                # Валидация
                "validation": validation,

                # Дополнительно
                "liq_price_estimate": round(liq_price_estimate, 2) if liq_price_estimate else None
            }

            return result

        except Exception as e:
            logger.exception(f"Error in position size calculation: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _round_qty(self, qty: float, qty_step: str) -> Tuple[Decimal, str]:
        """
        Округлить количество до qtyStep с использованием Decimal

        Args:
            qty: Сырое количество
            qty_step: Шаг округления (e.g., "0.001")

        Returns:
            (qty_decimal, qty_string)

        Example:
            >>> _round_qty(1.4723, "0.001")
            (Decimal('1.472'), '1.472')
        """
        qty_dec = Decimal(str(qty))
        step_dec = Decimal(str(qty_step))

        # Округление ВНИЗ (чтобы не превысить риск)
        rounded = (qty_dec / step_dec).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_dec

        return rounded, str(rounded)

    def _round_price(self, price: float, tick_size: str) -> Tuple[Decimal, str]:
        """
        Округлить цену до tickSize

        Args:
            price: Сырая цена
            tick_size: Шаг цены (e.g., "0.1")

        Returns:
            (price_decimal, price_string)
        """
        price_dec = Decimal(str(price))
        tick_dec = Decimal(str(tick_size))

        # Округление к ближайшему
        rounded = (price_dec / tick_dec).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * tick_dec

        return rounded, str(rounded)

    def _estimate_liquidation_price(
        self,
        entry_price: float,
        leverage: int,
        side: str
    ) -> Optional[float]:
        """
        Оценить ликвидационную цену (упрощённая формула)

        Формула (изолированная маржа):
        - Long: liq_price = entry * (1 - 1/leverage * 0.9)
        - Short: liq_price = entry * (1 + 1/leverage * 0.9)

        (0.9 = 90% учёт комиссий, не 100% точно но близко)

        Args:
            entry_price: Цена входа
            leverage: Плечо
            side: "long" | "short"

        Returns:
            Ликвидационная цена (approx)
        """
        if leverage <= 1:
            return None

        # Simplified formula for isolated margin
        liq_buffer = 1.0 / leverage * 0.9

        if side == "long":
            liq_price = entry_price * (1 - liq_buffer)
        else:  # short
            liq_price = entry_price * (1 + liq_buffer)

        return liq_price

    def _validate_position(
        self,
        qty: Decimal,
        notional: float,
        margin_required: float,
        actual_risk_usd: float,
        params: PositionParams,
        instrument: InstrumentInfo
    ) -> Dict[str, Any]:
        """
        Валидировать позицию на соответствие ограничениям

        Returns:
            {
                "is_valid": bool,
                "warnings": [...],
                "errors": [...]
            }
        """
        warnings = []
        errors = []

        # 1. Проверка баланса
        if params.account_balance is not None:
            if margin_required > params.account_balance:
                errors.append(
                    f"Insufficient balance: need ${margin_required:.2f}, "
                    f"have ${params.account_balance:.2f}"
                )

        # 2. Проверка safety limits
        if params.max_risk is not None:
            if actual_risk_usd > params.max_risk:
                errors.append(
                    f"Risk ${actual_risk_usd:.2f} exceeds max ${params.max_risk:.2f}"
                )

        if params.max_margin is not None:
            if margin_required > params.max_margin:
                errors.append(
                    f"Margin ${margin_required:.2f} exceeds max ${params.max_margin:.2f}"
                )

        # 3. Проверка minNotional
        min_notional = float(instrument.min_notional)
        if notional < min_notional:
            errors.append(
                f"Position too small: ${notional:.2f} < min ${min_notional:.2f}"
            )

        # 4. Проверка qty limits
        min_qty = Decimal(instrument.min_order_qty)
        max_qty = Decimal(instrument.max_order_qty)

        if qty < min_qty:
            errors.append(
                f"Qty {qty} < min {min_qty}"
            )

        if qty > max_qty:
            errors.append(
                f"Qty {qty} > max {max_qty}"
            )

        # 5. Проверка leverage
        if params.leverage > instrument.max_leverage:
            errors.append(
                f"Leverage {params.leverage}x exceeds max {instrument.max_leverage}x"
            )

        # 6. Warnings for high leverage
        if params.leverage >= 10:
            warnings.append(
                f"⚠️ High leverage ({params.leverage}x) - small moves = liquidation!"
            )
        elif params.leverage >= 5:
            warnings.append(
                f"⚡ Moderate leverage ({params.leverage}x) - be careful!"
            )

        # 7. Warning for large risk
        if params.account_balance is not None:
            risk_pct = (actual_risk_usd / params.account_balance) * 100
            if risk_pct > 5:
                warnings.append(
                    f"⚠️ High risk: {risk_pct:.1f}% of account balance"
                )

        return {
            "is_valid": len(errors) == 0,
            "warnings": warnings if warnings else None,
            "errors": errors if errors else None
        }


# Singleton instance
position_size_calculator = PositionSizeCalculator()
