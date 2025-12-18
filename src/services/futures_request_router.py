# coding: utf-8
"""
Futures Request Router - GPT-4o-mini validator for futures signals

Это entry-point всей трейд-экосистемы Syntra - используется из:
- Telegram Bot (/futures command)
- Mini App (Signals toggle)
- Web Interface (Chat signals mode)
- API Partners

Роутер определяет:
1. Является ли запрос futures-сигналом
2. Достаточно ли данных для генерации
3. Confidence score (0.0-1.0)
4. Какие уточняющие вопросы задать

Thresholds:
- confidence >= 0.85 → auto-proceed to FuturesAnalysisService
- confidence < 0.60 → always ask clarification
- 0.60 <= confidence < 0.85 → proceed but log for analysis
"""
import json
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field

from openai import AsyncOpenAI
from loguru import logger

from config.config import OPENAI_API_KEY


# ==============================================================================
# MODELS
# ==============================================================================

class FuturesRequestValidation(BaseModel):
    """Result of request validation"""
    is_futures_request: bool = Field(description="Is this a futures/trading signal request?")
    has_sufficient_data: bool = Field(description="Does request have enough data to proceed?")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    ticker: Optional[str] = Field(default=None, description="Extracted ticker (e.g., BTCUSDT)")
    timeframe: Optional[str] = Field(default=None, description="Timeframe (1h, 4h, 1d)")
    timeframe_was_default: bool = Field(default=False, description="True if timeframe was defaulted")
    mode: str = Field(default="standard", description="Trading mode: conservative, standard, high_risk, meme")
    clarifying_questions: Optional[List[str]] = Field(default=None, description="Questions to ask user")
    raw_ticker: Optional[str] = Field(default=None, description="Original ticker before normalization")


class FuturesRouterConfig(BaseModel):
    """Router configuration"""
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 500
    confidence_auto_proceed: float = 0.85
    confidence_ask_anyway: float = 0.60
    default_timeframe: str = "4h"


# ==============================================================================
# CONSTANTS
# ==============================================================================

VALID_TIMEFRAMES = ["15m", "1h", "4h", "1d", "1w"]
VALID_MODES = ["conservative", "standard", "high_risk", "meme"]

# Common ticker aliases
TICKER_ALIASES = {
    "btc": "BTCUSDT",
    "bitcoin": "BTCUSDT",
    "биткоин": "BTCUSDT",
    "биток": "BTCUSDT",
    "битка": "BTCUSDT",
    "eth": "ETHUSDT",
    "ethereum": "ETHUSDT",
    "эфир": "ETHUSDT",
    "эфириум": "ETHUSDT",
    "sol": "SOLUSDT",
    "solana": "SOLUSDT",
    "солана": "SOLUSDT",
    "bnb": "BNBUSDT",
    "xrp": "XRPUSDT",
    "рипл": "XRPUSDT",
    "doge": "DOGEUSDT",
    "dogecoin": "DOGEUSDT",
    "дож": "DOGEUSDT",
    "ada": "ADAUSDT",
    "cardano": "ADAUSDT",
    "avax": "AVAXUSDT",
    "avalanche": "AVAXUSDT",
    "dot": "DOTUSDT",
    "polkadot": "DOTUSDT",
    "link": "LINKUSDT",
    "chainlink": "LINKUSDT",
    "matic": "MATICUSDT",
    "polygon": "MATICUSDT",
    "sui": "SUIUSDT",
    "apt": "APTUSDT",
    "aptos": "APTUSDT",
    "arb": "ARBUSDT",
    "arbitrum": "ARBUSDT",
    "op": "OPUSDT",
    "optimism": "OPUSDT",
    "pepe": "PEPEUSDT",
    "пепе": "PEPEUSDT",
    "shib": "SHIBUSDT",
    "bonk": "BONKUSDT",
    "wif": "WIFUSDT",
    "floki": "FLOKIUSDT",
    "near": "NEARUSDT",
    "ftm": "FTMUSDT",
    "fantom": "FTMUSDT",
    "ton": "TONUSDT",
    "тон": "TONUSDT",
    "atom": "ATOMUSDT",
    "cosmos": "ATOMUSDT",
    "inj": "INJUSDT",
    "injective": "INJUSDT",
    "sei": "SEIUSDT",
    "jup": "JUPUSDT",
    "jupiter": "JUPUSDT",
    "render": "RENDERUSDT",
    "rndr": "RENDERUSDT",
}

# Timeframe aliases
TIMEFRAME_ALIASES = {
    "15min": "15m",
    "15 min": "15m",
    "15 минут": "15m",
    "1hour": "1h",
    "1 hour": "1h",
    "1час": "1h",
    "1 час": "1h",
    "часовой": "1h",
    "часовик": "1h",
    "4hour": "4h",
    "4 hour": "4h",
    "4hours": "4h",
    "4 hours": "4h",
    "4часа": "4h",
    "4 часа": "4h",
    "четырёхчасовой": "4h",
    "4часовик": "4h",
    "1day": "1d",
    "1 day": "1d",
    "daily": "1d",
    "день": "1d",
    "1день": "1d",
    "1 день": "1d",
    "дневной": "1d",
    "дневка": "1d",
    "1week": "1w",
    "1 week": "1w",
    "weekly": "1w",
    "неделя": "1w",
    "1неделя": "1w",
    "1 неделя": "1w",
    "недельный": "1w",
    "недельник": "1w",
}

# Mode aliases
MODE_ALIASES = {
    "консервативный": "conservative",
    "консерватив": "conservative",
    "осторожный": "conservative",
    "safe": "conservative",
    "стандартный": "standard",
    "стандарт": "standard",
    "обычный": "standard",
    "normal": "standard",
    "агрессивный": "high_risk",
    "агрессив": "high_risk",
    "рисковый": "high_risk",
    "high risk": "high_risk",
    "highrisk": "high_risk",
    "aggressive": "high_risk",
    "мем": "meme",
    "мемкоин": "meme",
    "memecoin": "meme",
    "дегенский": "meme",
    "degen": "meme",
}


# ==============================================================================
# SYSTEM PROMPT
# ==============================================================================

ROUTER_SYSTEM_PROMPT = """You are a request classifier for a crypto trading AI assistant.

Your job is to analyze user messages and determine:
1. Is this a futures/trading signal request? (user wants entry/SL/TP levels)
2. How confident are you in this classification? (0.0-1.0)
3. If yes, extract: ticker, timeframe, trading mode
4. If data is missing OR confidence < 0.85, generate clarifying questions

## FUTURES SIGNAL REQUESTS (high confidence examples):
- "сигнал по BTC 4h" → is_futures: true, confidence: 0.95, ticker: BTC, tf: 4h
- "точки входа SOL 1d conservative" → is_futures: true, confidence: 0.98
- "entry levels for ETH" → is_futures: true, confidence: 0.90
- "куда входить в биткоин" → is_futures: true, confidence: 0.85
- "дай сетап на эфир часовик" → is_futures: true, confidence: 0.92

## AMBIGUOUS (low-medium confidence):
- "long ETH?" → is_futures: true, confidence: 0.70 (no timeframe, unclear if wants levels)
- "ну хз, наверное BTC?" → is_futures: true, confidence: 0.40 (very unclear intent)
- "что думаешь по SOL" → is_futures: false, confidence: 0.85 (wants analysis, not signal)

## NON-FUTURES (is_futures_request: false):
- "что по рынку?" → general market question
- "новости ETH" → news request
- "что такое funding rate" → educational question
- "почему BTC падает" → analysis question, not signal request
- "привет" → greeting

## TRADING MODES:
- conservative: safer entries, tighter stops, lower leverage
- standard: balanced approach (DEFAULT)
- high_risk: wider stops, higher leverage, larger targets
- meme: for memecoins, very high volatility expected

## CLARIFYING QUESTIONS:
Generate 1-3 specific questions in user's language when:
- Ticker is missing or ambiguous
- Timeframe not specified (but suggest 4h as default)
- Intent is unclear
- Confidence is low

IMPORTANT: If timeframe is not specified, you can proceed with 4h as default, but set has_sufficient_data: true and add a note that 4h will be used.

Return JSON only (no markdown):
{
  "is_futures_request": true/false,
  "confidence": 0.0-1.0,
  "has_sufficient_data": true/false,
  "ticker": "BTC" | null,
  "timeframe": "4h" | null,
  "mode": "standard",
  "clarifying_questions": ["Question 1?", "Question 2?"] | null
}"""


# ==============================================================================
# ROUTER CLASS
# ==============================================================================

class FuturesRequestRouter:
    """
    GPT-4o-mini powered request router for futures signals

    Entry-point for:
    - Telegram Bot
    - Mini App
    - Web Interface
    - API Partners
    """

    def __init__(self, config: Optional[FuturesRouterConfig] = None):
        self.config = config or FuturesRouterConfig()
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        logger.info(f"🚦 FuturesRequestRouter initialized (model: {self.config.model})")

    async def validate_request(
        self,
        user_message: str,
        language: str = "ru"
    ) -> FuturesRequestValidation:
        """
        Validate user request using GPT-4o-mini

        Args:
            user_message: User's message text
            language: User language for clarifying questions

        Returns:
            FuturesRequestValidation with all extracted data
        """
        logger.debug(f"🚦 Validating request: '{user_message[:100]}...' (lang={language})")

        try:
            # Call GPT-4o-mini
            response = await self.client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Language: {language}\nMessage: {user_message}"}
                ],
                response_format={"type": "json_object"}
            )

            # Parse response
            content = response.choices[0].message.content
            data = json.loads(content)

            logger.debug(f"🚦 Router response: {data}")

            # Build validation result
            result = self._build_validation_result(data, user_message, language)

            # Log decision
            self._log_routing_decision(result, user_message)

            return result

        except json.JSONDecodeError as e:
            logger.error(f"🚦 JSON parse error: {e}")
            return self._create_fallback_result(user_message, language)
        except Exception as e:
            logger.exception(f"🚦 Router error: {e}")
            return self._create_fallback_result(user_message, language)

    def _build_validation_result(
        self,
        data: dict,
        user_message: str,
        language: str
    ) -> FuturesRequestValidation:
        """Build validation result from GPT response"""

        is_futures = data.get("is_futures_request", False)
        confidence = float(data.get("confidence", 0.0))
        has_sufficient = data.get("has_sufficient_data", False)
        raw_ticker = data.get("ticker")
        raw_timeframe = data.get("timeframe")
        mode = data.get("mode", "standard")
        questions = data.get("clarifying_questions")

        # Normalize ticker
        ticker = None
        if raw_ticker:
            ticker = self.normalize_ticker(raw_ticker)

        # Normalize timeframe + handle default
        timeframe = None
        timeframe_was_default = False
        if raw_timeframe:
            timeframe, _ = self.validate_timeframe(raw_timeframe, language)
        elif is_futures and has_sufficient:
            # No timeframe specified but has other data → use default
            timeframe = self.config.default_timeframe
            timeframe_was_default = True

        # Normalize mode
        mode = self._normalize_mode(mode)

        # Build clarifying questions if needed
        if is_futures and confidence < self.config.confidence_ask_anyway:
            # Low confidence → always ask
            if not questions:
                questions = self._generate_clarifying_questions(
                    ticker, timeframe, confidence, language
                )
        elif is_futures and not has_sufficient and not questions:
            # Not enough data → generate questions
            questions = self._generate_clarifying_questions(
                ticker, timeframe, confidence, language
            )

        return FuturesRequestValidation(
            is_futures_request=is_futures,
            has_sufficient_data=has_sufficient or (ticker is not None),
            confidence=confidence,
            ticker=ticker,
            timeframe=timeframe,
            timeframe_was_default=timeframe_was_default,
            mode=mode,
            clarifying_questions=questions,
            raw_ticker=raw_ticker,
        )

    def normalize_ticker(self, ticker: str) -> str:
        """
        Normalize ticker to exchange format (BTCUSDT)

        Args:
            ticker: Raw ticker (BTC, bitcoin, биткоин, etc.)

        Returns:
            Normalized ticker (BTCUSDT)
        """
        ticker_lower = ticker.lower().strip()

        # Check aliases first
        if ticker_lower in TICKER_ALIASES:
            return TICKER_ALIASES[ticker_lower]

        # Already has USDT suffix
        ticker_upper = ticker.upper().strip()
        if ticker_upper.endswith("USDT"):
            return ticker_upper

        # Add USDT suffix
        return f"{ticker_upper}USDT"

    def validate_timeframe(
        self,
        timeframe: str,
        language: str
    ) -> Tuple[str, Optional[str]]:
        """
        Validate and normalize timeframe

        Args:
            timeframe: Raw timeframe from user
            language: User language for messages

        Returns:
            Tuple of (normalized_timeframe, explicit_message or None)
        """
        tf_lower = timeframe.lower().strip()

        # Check aliases
        if tf_lower in TIMEFRAME_ALIASES:
            tf_lower = TIMEFRAME_ALIASES[tf_lower]

        # Validate
        if tf_lower in VALID_TIMEFRAMES:
            return tf_lower, None

        # Invalid → return default with message
        default_tf = self.config.default_timeframe
        if language == "ru":
            message = f"⏱ Таймфрейм '{timeframe}' не поддерживается. Использую {default_tf.upper()} по умолчанию."
        else:
            message = f"⏱ Timeframe '{timeframe}' is not supported. Using {default_tf.upper()} by default."

        return default_tf, message

    def _normalize_mode(self, mode: str) -> str:
        """Normalize trading mode"""
        mode_lower = mode.lower().strip()

        if mode_lower in MODE_ALIASES:
            return MODE_ALIASES[mode_lower]

        if mode_lower in VALID_MODES:
            return mode_lower

        return "standard"

    def _generate_clarifying_questions(
        self,
        ticker: Optional[str],
        timeframe: Optional[str],
        confidence: float,
        language: str
    ) -> List[str]:
        """Generate clarifying questions based on missing data"""
        questions = []

        if language == "ru":
            if not ticker:
                questions.append("🪙 По какой монете нужен сигнал? (BTC, ETH, SOL...)")
            if not timeframe:
                questions.append("⏱ Какой таймфрейм? (1h, 4h, 1d) — или использую 4H по умолчанию")
            if confidence < 0.6 and ticker:
                questions.append("🎯 Ты хочешь получить точки входа, стоп-лосс и тейк-профиты?")
        else:
            if not ticker:
                questions.append("🪙 Which coin do you want a signal for? (BTC, ETH, SOL...)")
            if not timeframe:
                questions.append("⏱ What timeframe? (1h, 4h, 1d) — or I'll use 4H by default")
            if confidence < 0.6 and ticker:
                questions.append("🎯 Do you want entry points, stop-loss and take-profit levels?")

        return questions if questions else None

    def _create_fallback_result(
        self,
        user_message: str,
        language: str
    ) -> FuturesRequestValidation:
        """Create fallback result when router fails"""
        return FuturesRequestValidation(
            is_futures_request=False,
            has_sufficient_data=False,
            confidence=0.0,
            ticker=None,
            timeframe=None,
            timeframe_was_default=False,
            mode="standard",
            clarifying_questions=[
                "🤔 Не удалось распознать запрос. Уточни, что тебе нужно?" if language == "ru"
                else "🤔 Couldn't parse your request. Could you clarify what you need?"
            ],
        )

    def _log_routing_decision(
        self,
        result: FuturesRequestValidation,
        user_message: str
    ) -> None:
        """Log routing decision for analysis"""
        if result.is_futures_request:
            if result.confidence >= self.config.confidence_auto_proceed:
                logger.info(
                    f"🚦 AUTO-PROCEED: confidence={result.confidence:.2f}, "
                    f"ticker={result.ticker}, tf={result.timeframe}"
                )
            elif result.confidence >= self.config.confidence_ask_anyway:
                logger.info(
                    f"🚦 PROCEED-WITH-LOG: confidence={result.confidence:.2f}, "
                    f"ticker={result.ticker}, tf={result.timeframe}"
                )
            else:
                logger.info(
                    f"🚦 ASK-CLARIFICATION: confidence={result.confidence:.2f}, "
                    f"questions={result.clarifying_questions}"
                )
        else:
            logger.debug(f"🚦 NOT-FUTURES: confidence={result.confidence:.2f}")

    def should_auto_proceed(self, result: FuturesRequestValidation) -> bool:
        """Check if should auto-proceed to generation"""
        return (
            result.is_futures_request and
            result.has_sufficient_data and
            result.confidence >= self.config.confidence_auto_proceed and
            result.ticker is not None
        )

    def should_ask_clarification(self, result: FuturesRequestValidation) -> bool:
        """Check if should ask clarifying questions"""
        if not result.is_futures_request:
            return False

        # Low confidence → always ask
        if result.confidence < self.config.confidence_ask_anyway:
            return True

        # Missing critical data
        if result.ticker is None:
            return True

        return False

    def get_default_message(self, result: FuturesRequestValidation, language: str) -> Optional[str]:
        """Get message about defaults used"""
        if result.timeframe_was_default:
            if language == "ru":
                return f"📊 Таймфрейм не указан. Использую {result.timeframe.upper()} по умолчанию."
            else:
                return f"📊 No timeframe specified. Using {result.timeframe.upper()} by default."
        return None


# ==============================================================================
# SINGLETON
# ==============================================================================

futures_request_router = FuturesRequestRouter()
