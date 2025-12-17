"""
Multi-Platform Authentication
- Telegram Mini App: HMAC-SHA256 validation of initData
- Web: NextAuth JWT validation
"""

import hashlib
import hmac
import time
import json
import os
from typing import Optional, Dict, Any
from urllib.parse import parse_qsl

from fastapi import HTTPException, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from loguru import logger

from src.database.crud import get_user_by_telegram_id, get_user_by_email, get_or_create_user
from src.database.models import User
from src.database.engine import get_session
from config.config import BOT_TOKEN

# NextAuth JWT secret (должен совпадать с NEXTAUTH_SECRET в .env.local фронтенда)
NEXTAUTH_SECRET = os.getenv('NEXTAUTH_SECRET', 'your-nextauth-secret-here')
NEXTAUTH_ALGORITHM = "HS256"

# Expiration time для initData (по умолчанию 24 часа = 86400 секунд)
INIT_DATA_EXPIRATION = int(os.getenv('INIT_DATA_EXPIRATION', '86400'))


def validate_telegram_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """
    Validate Telegram initData using HMAC-SHA256

    Process:
    1. Parse init data parameters
    2. Extract and verify hash
    3. Check auth_date expiration (5 minutes)
    4. Create HMAC-SHA256 signature using bot token
    5. Compare signatures

    Args:
        init_data: Raw initData string from Telegram WebApp
        bot_token: Bot token for signature validation

    Returns:
        dict: Parsed and validated init data

    Raises:
        HTTPException: If validation fails
    """
    try:
        # Parse init data to dict
        parsed_data = dict(parse_qsl(init_data))

        # Extract hash (signature from Telegram)
        received_hash = parsed_data.get('hash')
        if not received_hash:
            raise HTTPException(
                status_code=401,
                detail="Missing hash in init data"
            )

        # Extract auth_date and check expiration (5 minutes)
        auth_date = parsed_data.get('auth_date')
        if not auth_date:
            raise HTTPException(
                status_code=401,
                detail="Missing auth_date in init data"
            )

        auth_timestamp = int(auth_date)
        current_timestamp = int(time.time())

        # Check if initData is not expired (default: 24 hours = 86400 seconds)
        time_elapsed = current_timestamp - auth_timestamp
        if time_elapsed > INIT_DATA_EXPIRATION:
            hours_elapsed = time_elapsed / 3600
            raise HTTPException(
                status_code=401,
                detail=f"Init data expired ({hours_elapsed:.1f} hours old, limit: {INIT_DATA_EXPIRATION / 3600:.1f} hours)"
            )

        # Prepare data check string (all params except hash, sorted alphabetically)
        data_check_arr = []
        for key in sorted(parsed_data.keys()):
            if key == 'hash':
                continue
            value = parsed_data[key]
            data_check_arr.append(f"{key}={value}")

        data_check_string = '\n'.join(data_check_arr)

        # Step 1: Create secret key from bot token
        # HMAC-SHA256 of bot_token using "WebAppData" as key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()

        # Step 2: Create signature of data_check_string using secret_key
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        # Compare hashes
        if calculated_hash != received_hash:
            raise HTTPException(
                status_code=401,
                detail="Invalid hash - signature verification failed"
            )

        # Parse user data from JSON string
        user_data = {}
        if 'user' in parsed_data:
            try:
                user_data = json.loads(parsed_data['user'])
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid user data format"
                )

        return {
            'user': user_data,
            'auth_date': auth_timestamp,
            'query_id': parsed_data.get('query_id'),
            'chat_instance': parsed_data.get('chat_instance'),
            'start_param': parsed_data.get('start_param'),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Init data validation failed: {str(e)}"
        )


def decode_nextauth_jwt(token: str) -> Dict[str, Any]:
    """
    Decode and validate NextAuth JWT token.

    Args:
        token: JWT token from NextAuth

    Returns:
        dict: Decoded JWT payload with user data

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            NEXTAUTH_SECRET,
            algorithms=[NEXTAUTH_ALGORITHM]
        )

        # Validate required fields
        if not payload.get('email'):
            raise HTTPException(
                status_code=401,
                detail="Missing email in JWT payload"
            )

        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid JWT token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"JWT validation failed: {str(e)}"
        )


async def get_current_user(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session)
) -> User:
    """
    FastAPI Dependency для получения текущего пользователя.
    Поддерживает multi-platform authentication:
    - Telegram Mini App: "tma <initDataRaw>"
    - Web (NextAuth): "Bearer <jwt_token>"

    Args:
        authorization: Authorization header
        session: Database session

    Returns:
        User: Authenticated user from database

    Raises:
        HTTPException: If authentication fails

    Usage:
        @router.get("/profile")
        async def get_profile(user: User = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    # Telegram Mini App authentication
    if authorization.startswith('tma '):
        # Extract initData
        init_data_raw = authorization[4:]  # Remove "tma " prefix

        # Validate initData
        init_data = validate_telegram_init_data(init_data_raw, BOT_TOKEN)

        # Get user from database
        if not init_data.get('user'):
            raise HTTPException(
                status_code=401,
                detail="No user data in init data"
            )

        telegram_id = init_data['user']['id']
        telegram_user = init_data['user']

        # Auto-create user if not exists (like bot's DatabaseMiddleware)
        user, is_new = await get_or_create_user(
            session,
            telegram_id=telegram_id,
            username=telegram_user.get('username'),
            first_name=telegram_user.get('first_name'),
            last_name=telegram_user.get('last_name'),
            photo_url=telegram_user.get('photo_url'),
            telegram_language=telegram_user.get('language_code'),
        )

        if is_new:
            logger.info(f"Auto-created user from Mini App: telegram_id={telegram_id}, username={telegram_user.get('username')}")

        # Check if user is banned
        if user.is_banned:
            raise HTTPException(
                status_code=403,
                detail="Your account has been suspended"
            )

        return user

    # Web (NextAuth) authentication
    elif authorization.startswith('Bearer '):
        # Extract JWT token
        token = authorization[7:]  # Remove "Bearer " prefix

        # Decode and validate JWT
        payload = decode_nextauth_jwt(token)

        # Get user by email
        email = payload.get('email')
        if not email:
            raise HTTPException(
                status_code=401,
                detail="Missing email in JWT payload"
            )

        user = await get_user_by_email(session, email)

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User not found (email: {email})"
            )

        # Check if user is banned
        if user.is_banned:
            raise HTTPException(
                status_code=403,
                detail="Your account has been suspended"
            )

        return user

    # Invalid auth header format
    else:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header. Expected: 'tma <initData>' or 'Bearer <token>'"
        )


# Tuple type for user+session dependency
from typing import Tuple


async def get_current_user_with_session(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session)
) -> Tuple[User, AsyncSession]:
    """
    Get current user AND the session together.
    Use this in endpoints that need to make additional DB queries.
    This ensures user and queries use the SAME session, avoiding greenlet issues.

    Usage:
        @router.get("/endpoint")
        async def handler(
            user_session: Tuple[User, AsyncSession] = Depends(get_current_user_with_session)
        ):
            user, session = user_session
            # Now use session for queries
    """
    # Telegram Mini App authentication
    if authorization.startswith('tma '):
        init_data_raw = authorization[4:]
        init_data = validate_telegram_init_data(init_data_raw, BOT_TOKEN)

        if not init_data.get('user'):
            raise HTTPException(status_code=401, detail="No user data in init data")

        telegram_id = init_data['user']['id']
        telegram_user = init_data['user']

        # Auto-create user if not exists (like bot's DatabaseMiddleware)
        user, is_new = await get_or_create_user(
            session,
            telegram_id=telegram_id,
            username=telegram_user.get('username'),
            first_name=telegram_user.get('first_name'),
            last_name=telegram_user.get('last_name'),
            photo_url=telegram_user.get('photo_url'),
            telegram_language=telegram_user.get('language_code'),
        )

        if is_new:
            logger.info(f"Auto-created user from Mini App (with_session): telegram_id={telegram_id}")

        if user.is_banned:
            raise HTTPException(status_code=403, detail="Your account has been suspended")

        return user, session

    # Web (NextAuth) authentication
    elif authorization.startswith('Bearer '):
        token = authorization[7:]
        payload = decode_nextauth_jwt(token)

        email = payload.get('email')
        if not email:
            raise HTTPException(status_code=401, detail="Missing email in JWT payload")

        user = await get_user_by_email(session, email)

        if not user:
            raise HTTPException(status_code=404, detail=f"User not found (email: {email})")

        if user.is_banned:
            raise HTTPException(status_code=403, detail="Your account has been suspended")

        return user, session

    else:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header. Expected: 'tma <initData>' or 'Bearer <token>'"
        )
