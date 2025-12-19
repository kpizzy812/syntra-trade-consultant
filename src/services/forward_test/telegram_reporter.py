"""
Forward Test Telegram Reporter

Daily summary и inline кнопки для Telegram.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from src.services.forward_test.models import (
    ForwardTestSnapshot,
    ForwardTestMonitorState,
    ForwardTestOutcome,
)
from src.services.forward_test.enums import OutcomeResult, ScenarioState
from src.services.forward_test.config import get_config
from config.config import BOT_TOKEN, ADMIN_IDS


class TelegramReporter:
    """
    Daily summary в Telegram с inline кнопками.

    Формат: HTML с emoji и структурированными блоками.
    """

    def __init__(self, bot: Optional[Bot] = None):
        """
        Инициализация reporter.

        Args:
            bot: aiogram Bot instance. Если None - создаётся из BOT_TOKEN.
        """
        self.bot = bot
        self._own_bot = False

    async def _get_bot(self) -> Bot:
        """Получить bot instance (lazy init)."""
        if self.bot is None:
            from aiogram.client.default import DefaultBotProperties
            self.bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            self._own_bot = True
        return self.bot

    async def close(self):
        """Закрыть bot session если создан нами."""
        if self._own_bot and self.bot:
            await self.bot.session.close()
            self.bot = None
            self._own_bot = False

    async def send_daily_report(
        self,
        session: AsyncSession,
        target_date: Optional[date] = None,
        chat_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Отправить daily report всем админам.

        Args:
            session: DB session
            target_date: Дата отчёта (default: today)
            chat_ids: Кому слать (default: ADMIN_IDS)

        Returns:
            {"sent": N, "failed": N, "errors": [...]}
        """
        if target_date is None:
            target_date = date.today()

        if chat_ids is None:
            chat_ids = ADMIN_IDS

        if not chat_ids:
            logger.warning("[FT Reporter] No chat_ids to send report")
            return {"sent": 0, "failed": 0, "errors": ["No recipients"]}

        # Build report
        report_html = await self._build_daily_report(session, target_date)
        keyboard = self._build_inline_keyboard()

        bot = await self._get_bot()
        sent = 0
        failed = 0
        errors = []

        for chat_id in chat_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=report_html,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                sent += 1
                logger.info(f"[FT Reporter] Sent daily report to {chat_id}")
            except TelegramForbiddenError:
                failed += 1
                errors.append(f"Forbidden: {chat_id}")
                logger.warning(f"[FT Reporter] Blocked by user {chat_id}")
            except TelegramBadRequest as e:
                failed += 1
                errors.append(f"BadRequest: {chat_id} - {e}")
                logger.error(f"[FT Reporter] Bad request for {chat_id}: {e}")
            except Exception as e:
                failed += 1
                errors.append(f"Error: {chat_id} - {e}")
                logger.error(f"[FT Reporter] Failed to send to {chat_id}: {e}")

        return {"sent": sent, "failed": failed, "errors": errors}

    async def _build_daily_report(
        self,
        session: AsyncSession,
        target_date: date
    ) -> str:
        """
        Построить HTML текст daily report.

        Format per plan:
        - Header с датой и universe
        - Funnel: generated → triggered → entered → finished
        - Performance: WR, Net R, Avg R, EV accuracy
        - Risk: Max DD, MAE/MFE p90
        - Best/Worst archetypes
        - Alerts
        - Learning queue
        """
        config = get_config()
        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time())

        # === Collect metrics ===

        # Funnel
        funnel = await self._get_funnel(session, start_dt, end_dt)

        # Performance
        perf = await self._get_performance(session, start_dt, end_dt)

        # Best/Worst archetypes
        best_arch = await self._get_archetype_stats(session, start_dt, end_dt, best=True)
        worst_arch = await self._get_archetype_stats(session, start_dt, end_dt, best=False)

        # Alerts
        alerts = self._generate_alerts(funnel, perf)

        # Batches count
        batches_q = select(func.count(func.distinct(ForwardTestSnapshot.batch_id))).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        )
        batches_count = (await session.execute(batches_q)).scalar() or 0

        # === Build HTML ===

        lines = [
            f"<b>Syntra Forward Test</b> — <i>last 24h</i>",
            "",
            f"<b>Universe:</b> {'/'.join(s.replace('USDT', '') for s in config.universe.symbols)} • "
            f"{', '.join(config.universe.timeframes)} • {', '.join(config.universe.modes)}",
            f"<b>Batches:</b> {batches_count}  (00/06/12/18 UTC)",
            "",
        ]

        # Funnel
        lines.append("<b>Funnel</b>")
        lines.append(f"• Generated: <b>{funnel['generated']}</b>")
        lines.append(f"• Triggered: <b>{funnel['triggered']}</b>  (<b>{funnel['trigger_rate']:.0f}%</b>)")
        lines.append(f"• Entered:   <b>{funnel['entered']}</b>  (<b>{funnel['entry_rate']:.0f}%</b>)")
        lines.append(f"• Finished:  <b>{funnel['finished']}</b>  (<b>{funnel['finish_rate']:.0f}%</b> of entered)")
        lines.append("")

        # Performance
        lines.append("<b>Performance</b>")
        if perf['total'] > 0:
            lines.append(f"• Winrate: <b>{perf['winrate']:.0f}%</b>  "
                        f"(W{perf['wins']} / L{perf['losses']} / BE{perf['breakeven']})")
            lines.append(f"• Net R: <b>{perf['total_r']:+.2f}R</b> ({perf['total']} finished)")
            lines.append(f"• Avg R: <b>{perf['avg_r']:+.2f}R</b>")
            if perf['ev_corr'] is not None:
                lines.append(f"• EV accuracy (corr): <b>{perf['ev_corr']:.2f}</b>")
            if perf['median_hold']:
                hold_h = perf['median_hold'] // 3600
                hold_m = (perf['median_hold'] % 3600) // 60
                lines.append(f"• Median time-to-exit: <b>{hold_h}h {hold_m}m</b>")
        else:
            lines.append("• No finished trades yet")
        lines.append("")

        # Risk
        if perf['mae_p90'] is not None or perf['mfe_p90'] is not None:
            lines.append("<b>Risk</b>")
            if perf['mae_p90'] is not None:
                lines.append(f"• MAE p90: <b>{perf['mae_p90']:.2f}R</b>")
            if perf['mfe_p90'] is not None:
                lines.append(f"• MFE p90: <b>{perf['mfe_p90']:+.2f}R</b>")
            lines.append("")

        # Best archetype
        if best_arch:
            lines.append("<b>Best archetype</b>")
            lines.append(f"• {best_arch['archetype']}: <b>{best_arch['avg_r']:+.2f}R</b> (n={best_arch['count']})")
            lines.append("")

        # Worst archetype
        if worst_arch:
            lines.append("<b>Worst archetype</b>")
            lines.append(f"• {worst_arch['archetype']}: <b>{worst_arch['avg_r']:+.2f}R</b> (n={worst_arch['count']})")
            lines.append("")

        # Alerts
        if alerts:
            lines.append("<b>Alerts</b>")
            for alert in alerts:
                icon = "" if alert['severity'] == 'critical' else ""
                lines.append(f"{icon} {alert['message']}")
            lines.append("")

        # Learning
        lines.append("<b>Learning</b>")
        lines.append(f"Paper outcomes queued: <b>{perf['total']}</b> (weight {config.learning_gates.paper_weight})")

        return "\n".join(lines)

    async def _get_funnel(
        self,
        session: AsyncSession,
        start_dt: datetime,
        end_dt: datetime
    ) -> Dict[str, Any]:
        """Получить funnel метрики."""
        # Generated
        gen_q = select(func.count()).select_from(ForwardTestSnapshot).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        )
        generated = (await session.execute(gen_q)).scalar() or 0

        # Triggered
        trig_q = select(func.count()).select_from(ForwardTestMonitorState).join(
            ForwardTestSnapshot,
            ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt,
                ForwardTestMonitorState.triggered_at.isnot(None)
            )
        )
        triggered = (await session.execute(trig_q)).scalar() or 0

        # Entered
        ent_q = select(func.count()).select_from(ForwardTestMonitorState).join(
            ForwardTestSnapshot,
            ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt,
                ForwardTestMonitorState.entered_at.isnot(None)
            )
        )
        entered = (await session.execute(ent_q)).scalar() or 0

        # Finished
        fin_q = select(func.count()).select_from(ForwardTestOutcome).join(
            ForwardTestSnapshot,
            ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        )
        finished = (await session.execute(fin_q)).scalar() or 0

        return {
            "generated": generated,
            "triggered": triggered,
            "entered": entered,
            "finished": finished,
            "trigger_rate": triggered / generated * 100 if generated > 0 else 0,
            "entry_rate": entered / generated * 100 if generated > 0 else 0,
            "finish_rate": finished / entered * 100 if entered > 0 else 0,
        }

    async def _get_performance(
        self,
        session: AsyncSession,
        start_dt: datetime,
        end_dt: datetime
    ) -> Dict[str, Any]:
        """Получить performance метрики."""
        # Get outcomes
        outcomes_q = select(ForwardTestOutcome, ForwardTestSnapshot).join(
            ForwardTestSnapshot,
            ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        )
        result = await session.execute(outcomes_q)
        rows = result.all()

        if not rows:
            return {
                "total": 0, "wins": 0, "losses": 0, "breakeven": 0,
                "winrate": 0, "avg_r": 0, "total_r": 0,
                "ev_corr": None, "median_hold": None,
                "mae_p90": None, "mfe_p90": None
            }

        outcomes = [r[0] for r in rows]
        snapshots = [r[1] for r in rows]

        wins = sum(1 for o in outcomes if o.result == OutcomeResult.WIN.value)
        losses = sum(1 for o in outcomes if o.result == OutcomeResult.LOSS.value)
        breakeven = sum(1 for o in outcomes if o.result == OutcomeResult.BREAKEVEN.value)

        total_r = sum(o.total_r for o in outcomes)
        avg_r = total_r / len(outcomes) if outcomes else 0

        tradable = wins + losses + breakeven
        winrate = wins / tradable * 100 if tradable > 0 else 0

        # EV correlation
        ev_corr = None
        ev_pairs = [(s.ev_r, o.total_r) for s, o in zip(snapshots, outcomes) if s.ev_r is not None]
        if len(ev_pairs) >= 5:
            predicted = [p[0] for p in ev_pairs]
            realized = [p[1] for p in ev_pairs]
            n = len(predicted)
            mean_p = sum(predicted) / n
            mean_r = sum(realized) / n
            cov = sum((p - mean_p) * (r - mean_r) for p, r in zip(predicted, realized)) / n
            std_p = (sum((p - mean_p) ** 2 for p in predicted) / n) ** 0.5
            std_r = (sum((r - mean_r) ** 2 for r in realized) / n) ** 0.5
            if std_p > 0 and std_r > 0:
                ev_corr = cov / (std_p * std_r)

        # Median hold time
        hold_times = [o.hold_time_sec for o in outcomes if o.hold_time_sec]
        median_hold = sorted(hold_times)[len(hold_times) // 2] if hold_times else None

        # MAE/MFE p90
        mae_values = sorted([o.mae_r for o in outcomes if o.mae_r is not None])
        mfe_values = sorted([o.mfe_r for o in outcomes if o.mfe_r is not None])
        mae_p90 = mae_values[int(len(mae_values) * 0.9)] if mae_values else None
        mfe_p90 = mfe_values[int(len(mfe_values) * 0.9)] if mfe_values else None

        return {
            "total": len(outcomes),
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "winrate": winrate,
            "avg_r": avg_r,
            "total_r": total_r,
            "ev_corr": ev_corr,
            "median_hold": median_hold,
            "mae_p90": mae_p90,
            "mfe_p90": mfe_p90,
        }

    async def _get_archetype_stats(
        self,
        session: AsyncSession,
        start_dt: datetime,
        end_dt: datetime,
        best: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Получить best/worst archetype."""
        q = select(
            ForwardTestSnapshot.archetype,
            func.count().label('count'),
            func.avg(ForwardTestOutcome.total_r).label('avg_r')
        ).join(
            ForwardTestOutcome,
            ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        ).group_by(ForwardTestSnapshot.archetype).having(func.count() >= 2)

        if best:
            q = q.order_by(desc('avg_r'))
        else:
            q = q.order_by('avg_r')

        q = q.limit(1)

        result = await session.execute(q)
        row = result.first()

        if not row:
            return None

        return {
            "archetype": row[0],
            "count": row[1],
            "avg_r": row[2]
        }

    def _generate_alerts(
        self,
        funnel: Dict[str, Any],
        perf: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Сгенерировать алерты."""
        alerts = []

        # Low winrate
        if perf['total'] >= 10 and perf['winrate'] < 40:
            alerts.append({
                "severity": "warning",
                "type": "low_winrate",
                "message": f"Low winrate: {perf['winrate']:.0f}%"
            })

        # Negative edge
        if perf['total'] >= 10 and perf['avg_r'] < -0.1:
            alerts.append({
                "severity": "critical",
                "type": "negative_edge",
                "message": f"Negative edge: avg_r={perf['avg_r']:.2f}R"
            })

        # Poor EV correlation
        if perf['ev_corr'] is not None and perf['ev_corr'] < 0.1:
            alerts.append({
                "severity": "warning",
                "type": "ev_drift",
                "message": f"Poor EV accuracy: corr={perf['ev_corr']:.2f}"
            })

        # High expiration rate (from funnel)
        if funnel['generated'] > 10:
            exp_rate = (funnel['generated'] - funnel['entered']) / funnel['generated']
            if exp_rate > 0.5:
                alerts.append({
                    "severity": "warning",
                    "type": "low_conversion",
                    "message": f"Low entry rate: {funnel['entry_rate']:.0f}%"
                })

        return alerts

    def _build_inline_keyboard(self) -> InlineKeyboardMarkup:
        """
        Построить inline keyboard.

        Row 1: [7d] [Funnel]
        Row 2: [Best/Worst] [Alerts]
        Row 3: [Last batch] [Scenarios]
        Row 4: [Settings]
        """
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="7d", callback_data="ft:report:7d"),
                InlineKeyboardButton(text="Funnel", callback_data="ft:funnel"),
            ],
            [
                InlineKeyboardButton(text="Best/Worst", callback_data="ft:archetypes"),
                InlineKeyboardButton(text="Alerts", callback_data="ft:alerts"),
            ],
            [
                InlineKeyboardButton(text="Last batch", callback_data="ft:batch:last"),
                InlineKeyboardButton(text="Scenarios", callback_data="ft:scenarios"),
            ],
            [
                InlineKeyboardButton(text="Settings", callback_data="ft:settings"),
            ],
        ])


# =============================================================================
# Telegram Commands Handler (для /ft команд)
# =============================================================================

class ForwardTestCommandHandler:
    """
    Обработчик /ft команд в Telegram.

    Команды:
    - /ft - Daily report
    - /ft 7d - 7-дневный итог
    - /ft losers - Топ-10 лузеров
    - /ft archetype <name> - Stats по архетипу
    - /ft scenario <id> - Детали сценария
    - /ft batch - Последний batch
    - /ft symbols - Breakdown по символам
    """

    def __init__(self, reporter: TelegramReporter):
        self.reporter = reporter

    async def handle_command(
        self,
        session: AsyncSession,
        chat_id: int,
        command: str,
        args: List[str]
    ) -> bool:
        """
        Обработать /ft команду.

        Returns:
            True если команда обработана
        """
        bot = await self.reporter._get_bot()

        if not args:
            # /ft - daily report
            await self.reporter.send_daily_report(session, chat_ids=[chat_id])
            return True

        subcommand = args[0].lower()

        if subcommand == "7d":
            await self._send_7d_report(session, bot, chat_id)
            return True

        if subcommand == "losers":
            await self._send_losers_report(session, bot, chat_id)
            return True

        if subcommand == "archetype" and len(args) > 1:
            await self._send_archetype_stats(session, bot, chat_id, args[1])
            return True

        if subcommand == "scenario" and len(args) > 1:
            await self._send_scenario_detail(session, bot, chat_id, args[1])
            return True

        if subcommand == "batch":
            await self._send_last_batch(session, bot, chat_id)
            return True

        if subcommand == "symbols":
            await self._send_symbols_breakdown(session, bot, chat_id)
            return True

        return False

    async def _send_7d_report(
        self,
        session: AsyncSession,
        bot: Bot,
        chat_id: int
    ):
        """7-дневный сводный отчёт."""
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)

        perf = await self.reporter._get_performance(session, start_dt, end_dt)

        lines = [
            "<b>Syntra Forward Test</b> — <i>7 days</i>",
            "",
            f"<b>Total trades:</b> {perf['total']}",
            f"<b>Winrate:</b> {perf['winrate']:.0f}%",
            f"<b>Net R:</b> {perf['total_r']:+.2f}R",
            f"<b>Avg R:</b> {perf['avg_r']:+.2f}R",
        ]

        if perf['ev_corr'] is not None:
            lines.append(f"<b>EV corr:</b> {perf['ev_corr']:.2f}")

        await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML)

    async def _send_losers_report(
        self,
        session: AsyncSession,
        bot: Bot,
        chat_id: int
    ):
        """Топ-10 худших архетипов."""
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)

        q = select(
            ForwardTestSnapshot.archetype,
            func.count().label('count'),
            func.avg(ForwardTestOutcome.total_r).label('avg_r')
        ).join(
            ForwardTestOutcome,
            ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        ).group_by(ForwardTestSnapshot.archetype).having(
            func.count() >= 3
        ).order_by('avg_r').limit(10)

        result = await session.execute(q)
        rows = result.all()

        lines = ["<b>Top Losers (30d)</b>", ""]
        for i, row in enumerate(rows, 1):
            lines.append(f"{i}. {row[0]}: <b>{row[2]:+.2f}R</b> (n={row[1]})")

        if not rows:
            lines.append("No data yet")

        await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML)

    async def _send_archetype_stats(
        self,
        session: AsyncSession,
        bot: Bot,
        chat_id: int,
        archetype: str
    ):
        """Stats по конкретному архетипу."""
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)

        q = select(ForwardTestOutcome).join(
            ForwardTestSnapshot,
            ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt,
                ForwardTestSnapshot.archetype == archetype
            )
        )
        result = await session.execute(q)
        outcomes = result.scalars().all()

        if not outcomes:
            await bot.send_message(
                chat_id=chat_id,
                text=f"No data for archetype: {archetype}",
                parse_mode=ParseMode.HTML
            )
            return

        wins = sum(1 for o in outcomes if o.result == OutcomeResult.WIN.value)
        total_r = sum(o.total_r for o in outcomes)
        avg_r = total_r / len(outcomes)

        lines = [
            f"<b>Archetype: {archetype}</b>",
            "",
            f"<b>Trades:</b> {len(outcomes)}",
            f"<b>Wins:</b> {wins} ({wins / len(outcomes) * 100:.0f}%)",
            f"<b>Total R:</b> {total_r:+.2f}R",
            f"<b>Avg R:</b> {avg_r:+.2f}R",
        ]

        await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML)

    async def _send_scenario_detail(
        self,
        session: AsyncSession,
        bot: Bot,
        chat_id: int,
        snapshot_id: str
    ):
        """Детали сценария."""
        q = select(ForwardTestSnapshot, ForwardTestMonitorState, ForwardTestOutcome).outerjoin(
            ForwardTestMonitorState,
            ForwardTestSnapshot.snapshot_id == ForwardTestMonitorState.snapshot_id
        ).outerjoin(
            ForwardTestOutcome,
            ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
        ).where(ForwardTestSnapshot.snapshot_id == snapshot_id)

        result = await session.execute(q)
        row = result.first()

        if not row:
            await bot.send_message(chat_id=chat_id, text="Scenario not found")
            return

        snapshot, monitor, outcome = row

        lines = [
            f"<b>Scenario: {snapshot.snapshot_id[:8]}...</b>",
            "",
            f"<b>Symbol:</b> {snapshot.symbol} | {snapshot.timeframe}",
            f"<b>Bias:</b> {snapshot.bias}",
            f"<b>Archetype:</b> {snapshot.archetype}",
            f"<b>Confidence:</b> {snapshot.confidence:.0%}",
            "",
            f"<b>Entry:</b> {snapshot.entry_price_avg:.2f}",
            f"<b>SL:</b> {snapshot.stop_loss:.2f}",
            f"<b>TP1:</b> {snapshot.tp1_price:.2f}",
        ]

        if monitor:
            lines.append("")
            lines.append(f"<b>State:</b> {monitor.state}")
            if outcome:
                lines.append(f"<b>Result:</b> {outcome.result}")
                lines.append(f"<b>Total R:</b> {outcome.total_r:+.2f}R")

        await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML)

    async def _send_last_batch(
        self,
        session: AsyncSession,
        bot: Bot,
        chat_id: int
    ):
        """Последний batch."""
        q = select(
            ForwardTestSnapshot.batch_id,
            ForwardTestSnapshot.batch_ts,
            func.count().label('count')
        ).group_by(
            ForwardTestSnapshot.batch_id,
            ForwardTestSnapshot.batch_ts
        ).order_by(desc(ForwardTestSnapshot.batch_ts)).limit(1)

        result = await session.execute(q)
        row = result.first()

        if not row:
            await bot.send_message(chat_id=chat_id, text="No batches yet")
            return

        batch_id, batch_ts, count = row

        lines = [
            "<b>Last Batch</b>",
            "",
            f"<b>ID:</b> {batch_id[:8]}...",
            f"<b>Time:</b> {batch_ts.strftime('%Y-%m-%d %H:%M UTC')}",
            f"<b>Scenarios:</b> {count}",
        ]

        await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML)

    async def _send_symbols_breakdown(
        self,
        session: AsyncSession,
        bot: Bot,
        chat_id: int
    ):
        """Breakdown по символам."""
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)

        q = select(
            ForwardTestSnapshot.symbol,
            func.count().label('count'),
            func.avg(ForwardTestOutcome.total_r).label('avg_r')
        ).join(
            ForwardTestOutcome,
            ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        ).group_by(ForwardTestSnapshot.symbol).order_by(desc('avg_r'))

        result = await session.execute(q)
        rows = result.all()

        lines = ["<b>Symbols Breakdown (7d)</b>", ""]
        for row in rows:
            symbol = row[0].replace("USDT", "")
            lines.append(f"• {symbol}: <b>{row[2]:+.2f}R</b> (n={row[1]})")

        if not rows:
            lines.append("No data yet")

        await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML)
