# coding: utf-8
"""
Handlers for cryptocurrency commands (/price, /analyze, /market)
"""
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import ModelConfig
from config.prompt_selector import get_price_analysis_prompt
from src.services.openai_service import OpenAIService
from src.services.coingecko_service import CoinGeckoService
from src.services.cryptopanic_service import CryptoPanicService
from src.utils.coin_parser import normalize_coin_name, extract_coin_from_text


logger = logging.getLogger(__name__)

router = Router(name="crypto")

# Initialize services
openai_service = OpenAIService()
coingecko_service = CoinGeckoService()
cryptopanic_service = CryptoPanicService()


@router.message(Command("price"))
async def cmd_price(message: Message, command: CommandObject, session: AsyncSession):
    """
    Get price for cryptocurrency with brief analysis

    Usage: /price <coin>
    Example: /price bitcoin
    """
    user_id = message.from_user.id

    # Extract coin name from command
    if not command.args:
        await message.answer(
            "💰 <b>Команда /price</b>\n\n"
            "<b>Использование:</b> /price <монета>\n\n"
            "<b>Примеры:</b>\n"
            "• /price bitcoin\n"
            "• /price ethereum\n"
            "• /price BTC\n\n"
            "Я покажу текущую цену и дам краткий анализ."
        )
        return

    coin_query = command.args.strip()
    logger.info(f"Price command from user {user_id}: {coin_query}")

    # Normalize coin name
    coin_id = normalize_coin_name(coin_query)
    if not coin_id:
        # Try to extract from text
        detected = extract_coin_from_text(coin_query)
        if detected:
            coin_id = detected[0]
        else:
            await message.answer(
                f"❌ Не могу распознать монету: <b>{coin_query}</b>\n\n"
                "Попробуйте использовать полное название или символ:\n"
                "• bitcoin или BTC\n"
                "• ethereum или ETH\n"
                "• cardano или ADA"
            )
            return

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            # Get price data
            price_data = await coingecko_service.get_price(
                coin_id,
                include_24h_change=True,
                include_market_cap=True,
                include_24h_volume=True
            )

            if not price_data or coin_id not in price_data:
                await message.answer(
                    f"❌ Не удалось найти данные для <b>{coin_query}</b>\n\n"
                    "Проверьте правильность написания или попробуйте другое название."
                )
                return

            data = price_data[coin_id]

            # Get coin details for better name
            coin_details = await coingecko_service.get_coin_data(coin_id)
            coin_name = coin_details.get('name', coin_id.title()) if coin_details else coin_id.title()
            symbol = coin_details.get('symbol', '').upper() if coin_details else ''

            # Format price info
            price = data.get('usd', 0)
            change_24h = data.get('usd_24h_change', 0)
            market_cap = data.get('usd_market_cap', 0)
            volume_24h = data.get('usd_24h_vol', 0)

            # Emoji based on price change
            if change_24h > 0:
                emoji = "🟢"
                trend = "растёт"
            elif change_24h < 0:
                emoji = "🔴"
                trend = "падает"
            else:
                emoji = "⚪"
                trend = "стабильна"

            # Format response
            response = f"{emoji} <b>{coin_name} ({symbol})</b>\n\n"
            response += f"💰 <b>Цена:</b> ${price:,.2f}\n"
            response += f"📊 <b>Изменение 24ч:</b> {change_24h:+.2f}%\n"

            if market_cap:
                response += f"💎 <b>Капитализация:</b> ${market_cap:,.0f}\n"
            if volume_24h:
                response += f"📈 <b>Объём 24ч:</b> ${volume_24h:,.0f}\n"

            response += f"\n<i>Цена {trend} за последние 24 часа</i>"

            await message.answer(response)

            logger.info(f"Price info sent for {coin_id} to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in price command for user {user_id}: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при получении данных</b>\n\n"
            "Попробуйте позже или обратитесь к администратору."
        )


@router.message(Command("analyze"))
async def cmd_analyze(message: Message, command: CommandObject, session: AsyncSession, user_language: str = 'ru'):
    """
    Deep analysis of cryptocurrency with AI

    Usage: /analyze <coin>
    Example: /analyze bitcoin

    Args:
        message: Message with command
        command: Command object
        session: Database session
        user_language: User's language (from LanguageMiddleware)
    """
    user_id = message.from_user.id

    # Extract coin name from command
    if not command.args:
        await message.answer(
            "📊 <b>Команда /analyze</b>\n\n"
            "<b>Использование:</b> /analyze <монета>\n\n"
            "<b>Примеры:</b>\n"
            "• /analyze bitcoin\n"
            "• /analyze ethereum\n"
            "• /analyze SOL\n\n"
            "Я проведу полный анализ с техническими данными и новостным фоном."
        )
        return

    coin_query = command.args.strip()
    logger.info(f"Analyze command from user {user_id}: {coin_query}")

    # Normalize coin name
    coin_id = normalize_coin_name(coin_query)
    if not coin_id:
        detected = extract_coin_from_text(coin_query)
        if detected:
            coin_id = detected[0]
        else:
            await message.answer(
                f"❌ Не могу распознать монету: <b>{coin_query}</b>\n\n"
                "Попробуйте использовать полное название или символ."
            )
            return

    try:
        status_msg = await message.answer("⏳ <i>Собираю данные и анализирую...</i>")

        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            # Get price data
            price_data = await coingecko_service.get_price(
                coin_id,
                include_24h_change=True,
                include_market_cap=True,
                include_24h_volume=True
            )

            if not price_data or coin_id not in price_data:
                await status_msg.edit_text(
                    f"❌ Не удалось найти данные для <b>{coin_query}</b>"
                )
                return

            data = price_data[coin_id]

            # Get coin details
            coin_details = await coingecko_service.get_coin_data(coin_id)
            coin_name = coin_details.get('name', coin_id.title()) if coin_details else coin_id.title()
            symbol = coin_details.get('symbol', '').upper() if coin_details else ''

            # Get news
            news_items = await cryptopanic_service.get_news_for_coin(symbol, limit=3)
            news_text = cryptopanic_service.format_news_for_display(news_items, max_items=3)

            # Prepare data for AI
            price = data.get('usd', 0)
            change_24h = data.get('usd_24h_change', 0)
            market_cap = data.get('usd_market_cap', 0)
            volume_24h = data.get('usd_24h_vol', 0)

            # Build prompt for AI analysis using localized template
            analysis_prompt = get_price_analysis_prompt(
                language=user_language,
                coin_name=coin_name,
                current_price=price,
                change_24h=change_24h,
                market_cap=market_cap,
                volume_24h=volume_24h,
                news=news_text
            )

        # Stream AI analysis
        await status_msg.delete()

        sent_msg = await message.answer("⏳ <i>Анализирую...</i>")
        full_response = ""
        buffer = ""

        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            async for chunk in openai_service.stream_completion(
                session=session,
                user_id=user_id,
                user_message=analysis_prompt,
                user_language=user_language,
                model=ModelConfig.GPT_4O  # Use GPT-4O for detailed analysis
            ):
                if chunk:
                    full_response += chunk
                    buffer += chunk

                    # Update message every ~50 characters
                    if len(buffer) >= 50:
                        try:
                            await sent_msg.edit_text(full_response)
                            buffer = ""
                        except Exception:
                            pass  # Ignore edit errors

        # Final update
        if full_response:
            try:
                await sent_msg.edit_text(full_response)
            except Exception:
                pass

        logger.info(f"Analysis sent for {coin_id} to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in analyze command for user {user_id}: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при анализе</b>\n\n"
            "Попробуйте позже или обратитесь к администратору."
        )


@router.message(Command("market"))
async def cmd_market(message: Message, session: AsyncSession):
    """
    Show top cryptocurrencies by market cap

    Usage: /market
    """
    user_id = message.from_user.id
    logger.info(f"Market command from user {user_id}")

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            # Get top coins by market cap
            top_coins = await coingecko_service.get_trending_coins(limit=10)

            if not top_coins:
                await message.answer(
                    "❌ <b>Не удалось получить данные о рынке</b>\n\n"
                    "Попробуйте позже."
                )
                return

            # Format response
            response = "📊 <b>Топ-10 криптовалют по капитализации</b>\n\n"

            for i, coin in enumerate(top_coins, 1):
                name = coin.get('name', 'Unknown')
                symbol = coin.get('symbol', '').upper()
                price = coin.get('current_price', 0)
                change_24h = coin.get('price_change_percentage_24h', 0)
                market_cap = coin.get('market_cap', 0)

                # Emoji based on price change
                if change_24h > 0:
                    emoji = "🟢"
                elif change_24h < 0:
                    emoji = "🔴"
                else:
                    emoji = "⚪"

                response += f"{emoji} <b>{i}. {name} ({symbol})</b>\n"
                response += f"   ${price:,.2f} • {change_24h:+.2f}%\n"
                response += f"   Cap: ${market_cap/1e9:.2f}B\n\n"

            response += "<i>Данные предоставлены CoinGecko</i>"

            await message.answer(response)

            logger.info(f"Market data sent to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in market command for user {user_id}: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при получении данных о рынке</b>\n\n"
            "Попробуйте позже или обратитесь к администратору."
        )


@router.message(Command("news"))
async def cmd_news(message: Message, command: CommandObject):
    """
    Get latest cryptocurrency news

    Usage: /news [coin]
    Example: /news bitcoin
    """
    user_id = message.from_user.id
    coin_id = None

    # Check if coin specified
    if command.args:
        coin_query = command.args.strip()
        coin_id = normalize_coin_name(coin_query)
        if not coin_id:
            detected = extract_coin_from_text(coin_query)
            if detected:
                coin_id = detected[0]

    logger.info(f"News command from user {user_id}, coin: {coin_id}")

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            if coin_id:
                # Get news for specific coin
                coin_details = await coingecko_service.get_coin_data(coin_id)
                symbol = coin_details.get('symbol', coin_id).upper() if coin_details else coin_id.upper()

                news_items = await cryptopanic_service.get_news_for_coin(symbol, limit=5)
                coin_name = coin_details.get('name', coin_id.title()) if coin_details else coin_id.title()
                header = f"📰 <b>Новости: {coin_name}</b>\n\n"
            else:
                # Get trending news
                news_items = await cryptopanic_service.get_trending_news(limit=10)
                header = "📰 <b>Актуальные новости криптовалют</b>\n\n"

            if not news_items:
                await message.answer(
                    "❌ <b>Не удалось загрузить новости</b>\n\n"
                    "Попробуйте позже."
                )
                return

            news_text = cryptopanic_service.format_news_for_display(news_items)
            response = header + news_text

            await message.answer(response, disable_web_page_preview=True)

            logger.info(f"News sent to user {user_id}, coin: {coin_id}")

    except Exception as e:
        logger.exception(f"Error in news command for user {user_id}: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при получении новостей</b>\n\n"
            "Попробуйте позже или обратитесь к администратору."
        )
