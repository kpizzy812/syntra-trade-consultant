# coding: utf-8
"""
Handler for photo/image analysis (Vision functionality)
"""
import logging
from io import BytesIO

from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession
from openai import BadRequestError

from config.config import ModelConfig
from config.prompt_selector import get_question_vision_prompt
from src.services.openai_service import OpenAIService
from src.services.coingecko_service import CoinGeckoService
from src.utils.coin_parser import normalize_coin_name, extract_coin_from_text
from src.utils.i18n import i18n


logger = logging.getLogger(__name__)

router = Router(name="vision")

# Initialize services
openai_service = OpenAIService()
coingecko_service = CoinGeckoService()


@router.message(F.photo)
async def handle_photo(message: Message, session: AsyncSession, user_language: str = 'ru'):
    """
    Handle photo messages - analyze crypto charts with Vision API

    Args:
        message: Message with photo
        session: Database session (injected by middleware)
        user_language: User's language (from LanguageMiddleware)
    """
    user = message.from_user
    telegram_id = user.id
    username = user.username or user.first_name

    logger.info(f"Photo received from user {telegram_id} (@{username})")

    # Get database user
    from src.database.crud import get_or_create_user
    db_user, _ = await get_or_create_user(
        session,
        telegram_id=telegram_id,
        username=username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Get photo (largest size)
    photo = message.photo[-1]
    file_id = photo.file_id

    # Check file size (approximate)
    file_size = photo.file_size
    if file_size and file_size > ModelConfig.VISION_MAX_FILE_SIZE:
        await message.answer(
            i18n.get(
                'vision.file_too_large',
                user_language,
                max_size=ModelConfig.VISION_MAX_FILE_SIZE // (1024*1024)
            )
        )
        return

    try:
        # Show typing indicator while downloading and preparing
        async with ChatActionSender.upload_photo(
            bot=message.bot,
            chat_id=message.chat.id
        ):
            # Download photo
            file = await message.bot.get_file(file_id)
            photo_bytes = BytesIO()
            await message.bot.download_file(file.file_path, destination=photo_bytes)

            # Get image bytes
            image_bytes = photo_bytes.getvalue()

            # Step 1: Try to detect coin from image or caption
            coin_id = None
            market_data = None

            # First, check if user provided coin name in caption
            if message.caption:
                detected_coins = extract_coin_from_text(message.caption)
                if detected_coins:
                    coin_id = detected_coins[0]
                    logger.info(f"Detected coin from caption: {coin_id}")

            # If not found in caption, try to detect from image
            if not coin_id:
                logger.info("Attempting to detect coin from image...")
                detected_name = await openai_service.detect_coin_from_image(image_bytes, user_language)
                if detected_name:
                    coin_id = normalize_coin_name(detected_name)
                    if coin_id:
                        logger.info(f"Normalized coin ID: {coin_id}")

            # Step 2: Get market data if coin was detected
            if coin_id:
                logger.info(f"Fetching market data for {coin_id}...")
                price_data = await coingecko_service.get_price(
                    coin_id,
                    include_24h_change=True
                )

                if price_data and coin_id in price_data:
                    market_data = {
                        'name': coin_id.replace('-', ' ').title(),
                        'current_price': price_data[coin_id].get('usd', 0),
                        'price_change_percentage_24h': price_data[coin_id].get('usd_24h_change', 0),
                    }

                    # Try to get additional data
                    coin_details = await coingecko_service.get_coin_data(coin_id)
                    if coin_details:
                        market_data['total_volume'] = coin_details.get('market_data', {}).get('total_volume', {}).get('usd', 0)
                        market_data['market_cap'] = coin_details.get('market_data', {}).get('market_cap', {}).get('usd', 0)

                    logger.info(f"Market data fetched: ${market_data['current_price']:,.2f}")

            # Step 3: Build custom prompt if user provided caption
            user_prompt = None
            if message.caption and not extract_coin_from_text(message.caption):
                # Caption doesn't contain coin name, treat as question
                user_prompt = get_question_vision_prompt(
                    language=user_language,
                    user_question=message.caption,
                    coin_name=market_data['name'] if market_data else None,
                    current_price=market_data['current_price'] if market_data else None,
                    change_24h=market_data['price_change_percentage_24h'] if market_data else None
                )

        # Step 4: Build header for response
        coin_name_str = f" <b>{market_data['name'] if market_data else coin_id}</b>" if coin_id else ""

        # Add market data summary if available
        market_data_str = ""
        if market_data:
            price = market_data['current_price']
            change = market_data['price_change_percentage_24h']
            change_emoji = "🟢" if change > 0 else "🔴"

            market_data_str = i18n.get(
                'vision.current_data',
                user_language,
                price=f"{price:,.2f}",
                emoji=change_emoji,
                change=f"{change:+.2f}"
            )

        # Send initial message
        initial_msg = i18n.get('vision.analyzing', user_language, coin_name=coin_name_str)
        thinking_msg = await message.answer(
            initial_msg,
            parse_mode="HTML"
        )

        # Build response header for updates
        response_header = initial_msg.split('\n\n')[0] + "\n\n" + market_data_str

        # Step 5: Stream analysis with real-time updates
        import time
        full_analysis = ""
        last_update_time = time.time()
        last_update_length = 0

        STREAM_UPDATE_INTERVAL = 1.5  # Update message every 1.5 seconds
        MIN_CHARS_FOR_UPDATE = 100    # Or every 100 characters

        async with ChatActionSender.typing(
            bot=message.bot,
            chat_id=message.chat.id
        ):
            async for chunk in openai_service.stream_image_analysis(
                session=session,
                user_id=db_user.id,
                image_bytes=image_bytes,
                user_language=user_language,
                user_prompt=user_prompt,
                detail=ModelConfig.VISION_DETAIL_LEVEL,
                market_data=market_data
            ):
                full_analysis += chunk

                # Update message periodically or when enough new text
                current_time = time.time()
                chars_since_update = len(full_analysis) - last_update_length

                if (current_time - last_update_time >= STREAM_UPDATE_INTERVAL) or \
                   (chars_since_update >= MIN_CHARS_FOR_UPDATE):
                    try:
                        # Build current response
                        current_response = response_header + full_analysis

                        # Update message
                        await thinking_msg.edit_text(
                            current_response,
                            parse_mode="HTML"
                        )

                        last_update_time = current_time
                        last_update_length = len(full_analysis)
                    except Exception as e:
                        # Ignore rate limit or other editing errors
                        logger.debug(f"Error updating message during streaming: {e}")
                        pass

        # Final update with complete analysis and stats
        # Note: stats are tracked in stream_image_analysis, we need to calculate them here
        from src.utils.vision_tokens import calculate_image_tokens
        image_tokens = calculate_image_tokens(image_bytes, ModelConfig.VISION_DETAIL_LEVEL)
        prompt_tokens = openai_service.count_tokens(user_prompt or "")
        output_tokens = openai_service.count_tokens(full_analysis)
        total_tokens = image_tokens + prompt_tokens + output_tokens
        cost = openai_service.calculate_vision_cost(image_tokens + prompt_tokens, output_tokens)

        final_response = response_header + full_analysis
        final_response += f"\n\n<i>Токены: {total_tokens} (~${cost:.4f})</i>"

        await thinking_msg.edit_text(final_response, parse_mode="HTML")

        logger.info(
            f"Vision streaming analysis sent to user {telegram_id}. "
            f"Coin: {coin_id or 'unknown'}, "
            f"Tokens: {total_tokens}, Cost: ${cost:.4f}"
        )

    except BadRequestError as e:
        logger.error(f"Vision API BadRequest for user {telegram_id}: {e}")

        error_msg = str(e).lower()
        if "invalid" in error_msg or "format" in error_msg:
            await message.answer(i18n.get('vision.error_invalid_format', user_language))
        elif "size" in error_msg or "large" in error_msg:
            await message.answer(i18n.get('vision.error_size', user_language))
        else:
            await message.answer(i18n.get('vision.error_processing', user_language))

    except Exception as e:
        logger.exception(f"Error analyzing photo for user {telegram_id}: {e}")
        await message.answer(i18n.get('vision.error_general', user_language))


@router.message(F.document)
async def handle_document(message: Message, user_language: str = 'ru'):
    """
    Handle document messages - inform user to send as photo

    Some users send images as documents, we need to handle this

    Args:
        message: Message with document
        user_language: User's language (from LanguageMiddleware)
    """
    # Check if document is an image
    if message.document.mime_type and message.document.mime_type.startswith('image/'):
        await message.answer(i18n.get('vision.send_as_photo', user_language))
    else:
        # Not an image document - ignore or handle differently
        pass
