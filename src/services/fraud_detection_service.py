"""
Fraud Detection Service

Detects and prevents:
- Multi-trial abuse (telegram + email = 2x trial)
- Self-referral abuse
- Account sharing (same IP/fingerprint)

Uses fingerprinting and IP tracking to identify linked accounts.
"""

import json
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from src.database.models import (
    User,
    Subscription,
    DeviceFingerprint,
    LinkedAccount,
    LinkedAccountStatus,
    LinkedAccountType,
)


# ===========================
# CONFIGURATION
# ===========================

# Confidence score thresholds
CONFIDENCE_HIGH = 0.9  # Almost certainly same person
CONFIDENCE_MEDIUM = 0.7  # Likely same person
CONFIDENCE_LOW = 0.5  # Possibly same person

# Time windows for analysis
IP_MATCH_WINDOW_DAYS = 30  # Match IPs within last 30 days
FINGERPRINT_MATCH_WINDOW_DAYS = 90  # Match fingerprints within 90 days

# Minimum matches for flagging
MIN_IP_MATCHES = 2  # Need at least 2 IP matches
MIN_FINGERPRINT_MATCHES = 1  # Single fingerprint match is enough

# IPs to ignore (localhost, testing, etc.)
IGNORED_IPS = {
    "127.0.0.1",
    "::1",
    "localhost",
    "0.0.0.0",
}

# Known VPN/datacenter ASNs (high false positive rate)
VPN_ASNS = {
    "AS13335",  # Cloudflare
    "AS32934",  # Facebook
    # Add more as needed
}


# ===========================
# CRUD OPERATIONS - DeviceFingerprint
# ===========================


async def save_device_fingerprint(
    session: AsyncSession,
    user_id: int,
    ip_address: str,
    platform: str,
    event_type: str = "login",
    visitor_id: Optional[str] = None,
    fingerprint_hash: Optional[str] = None,
    user_agent: Optional[str] = None,
    device_type: Optional[str] = None,
    browser_name: Optional[str] = None,
    os_name: Optional[str] = None,
    screen_resolution: Optional[str] = None,
    timezone: Optional[str] = None,
    language: Optional[str] = None,
    telegram_device_model: Optional[str] = None,
    telegram_platform: Optional[str] = None,
    telegram_version: Optional[str] = None,
    ip_country: Optional[str] = None,
    ip_city: Optional[str] = None,
    ip_asn: Optional[str] = None,
) -> DeviceFingerprint:
    """
    Save device fingerprint for a user event

    Called on:
    - Registration (telegram or email)
    - Login
    - Payment
    - Referral code use
    """
    # Skip ignored IPs
    if ip_address in IGNORED_IPS:
        ip_address = "internal"

    fingerprint = DeviceFingerprint(
        user_id=user_id,
        ip_address=ip_address,
        platform=platform,
        event_type=event_type,
        visitor_id=visitor_id,
        fingerprint_hash=fingerprint_hash,
        user_agent=user_agent,
        device_type=device_type,
        browser_name=browser_name,
        os_name=os_name,
        screen_resolution=screen_resolution,
        timezone=timezone,
        language=language,
        telegram_device_model=telegram_device_model,
        telegram_platform=telegram_platform,
        telegram_version=telegram_version,
        ip_country=ip_country,
        ip_city=ip_city,
        ip_asn=ip_asn,
    )

    session.add(fingerprint)
    await session.commit()
    await session.refresh(fingerprint)

    logger.debug(f"Saved fingerprint for user {user_id}: IP={ip_address}, platform={platform}")
    return fingerprint


async def get_fingerprints_by_user(
    session: AsyncSession,
    user_id: int,
    limit: int = 100,
) -> List[DeviceFingerprint]:
    """Get all fingerprints for a user"""
    stmt = (
        select(DeviceFingerprint)
        .where(DeviceFingerprint.user_id == user_id)
        .order_by(DeviceFingerprint.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_users_by_ip(
    session: AsyncSession,
    ip_address: str,
    exclude_user_id: Optional[int] = None,
    days: int = IP_MATCH_WINDOW_DAYS,
) -> List[int]:
    """Get all user IDs that used this IP address"""
    if ip_address in IGNORED_IPS or ip_address == "internal":
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(DeviceFingerprint.user_id)
        .where(
            DeviceFingerprint.ip_address == ip_address,
            DeviceFingerprint.created_at >= cutoff,
        )
        .distinct()
    )

    if exclude_user_id:
        stmt = stmt.where(DeviceFingerprint.user_id != exclude_user_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_users_by_visitor_id(
    session: AsyncSession,
    visitor_id: str,
    exclude_user_id: Optional[int] = None,
    days: int = FINGERPRINT_MATCH_WINDOW_DAYS,
) -> List[int]:
    """Get all user IDs with this FingerprintJS visitor ID"""
    if not visitor_id:
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(DeviceFingerprint.user_id)
        .where(
            DeviceFingerprint.visitor_id == visitor_id,
            DeviceFingerprint.created_at >= cutoff,
        )
        .distinct()
    )

    if exclude_user_id:
        stmt = stmt.where(DeviceFingerprint.user_id != exclude_user_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_users_by_fingerprint_hash(
    session: AsyncSession,
    fingerprint_hash: str,
    exclude_user_id: Optional[int] = None,
    days: int = FINGERPRINT_MATCH_WINDOW_DAYS,
) -> List[int]:
    """Get all user IDs with this fingerprint hash"""
    if not fingerprint_hash:
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(DeviceFingerprint.user_id)
        .where(
            DeviceFingerprint.fingerprint_hash == fingerprint_hash,
            DeviceFingerprint.created_at >= cutoff,
        )
        .distinct()
    )

    if exclude_user_id:
        stmt = stmt.where(DeviceFingerprint.user_id != exclude_user_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())


# ===========================
# CRUD OPERATIONS - LinkedAccount
# ===========================


async def create_or_update_linked_account(
    session: AsyncSession,
    user_id_a: int,
    user_id_b: int,
    link_type: str,
    confidence_score: float,
    shared_ips: Optional[List[str]] = None,
    shared_fingerprints: Optional[List[str]] = None,
    shared_visitor_ids: Optional[List[str]] = None,
    evidence_details: Optional[Dict[str, Any]] = None,
) -> LinkedAccount:
    """
    Create or update linked account record

    Always stores user_id_a < user_id_b for uniqueness
    """
    # Ensure correct order
    if user_id_a > user_id_b:
        user_id_a, user_id_b = user_id_b, user_id_a

    # Check if link already exists
    stmt = select(LinkedAccount).where(
        LinkedAccount.user_id_a == user_id_a,
        LinkedAccount.user_id_b == user_id_b,
        LinkedAccount.link_type == link_type,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing link
        existing.confidence_score = max(existing.confidence_score, confidence_score)

        # Merge evidence
        if shared_ips:
            old_ips = json.loads(existing.shared_ips or "[]")
            new_ips = list(set(old_ips + shared_ips))
            existing.shared_ips = json.dumps(new_ips)

        if shared_fingerprints:
            old_fps = json.loads(existing.shared_fingerprints or "[]")
            new_fps = list(set(old_fps + shared_fingerprints))
            existing.shared_fingerprints = json.dumps(new_fps)

        if shared_visitor_ids:
            old_vids = json.loads(existing.shared_visitor_ids or "[]")
            new_vids = list(set(old_vids + shared_visitor_ids))
            existing.shared_visitor_ids = json.dumps(new_vids)

        if evidence_details:
            old_details = json.loads(existing.evidence_details or "{}")
            old_details.update(evidence_details)
            existing.evidence_details = json.dumps(old_details)

        await session.commit()
        await session.refresh(existing)
        return existing

    # Create new link
    link = LinkedAccount(
        user_id_a=user_id_a,
        user_id_b=user_id_b,
        link_type=link_type,
        confidence_score=confidence_score,
        shared_ips=json.dumps(shared_ips or []),
        shared_fingerprints=json.dumps(shared_fingerprints or []),
        shared_visitor_ids=json.dumps(shared_visitor_ids or []),
        evidence_details=json.dumps(evidence_details or {}),
    )

    session.add(link)
    await session.commit()
    await session.refresh(link)

    logger.info(
        f"Created linked account: users {user_id_a}-{user_id_b}, "
        f"type={link_type}, confidence={confidence_score:.2f}"
    )
    return link


async def get_linked_accounts_for_user(
    session: AsyncSession,
    user_id: int,
    status: Optional[str] = None,
) -> List[LinkedAccount]:
    """Get all linked accounts for a user"""
    stmt = select(LinkedAccount).where(
        or_(
            LinkedAccount.user_id_a == user_id,
            LinkedAccount.user_id_b == user_id,
        )
    )

    if status:
        stmt = stmt.where(LinkedAccount.status == status)

    stmt = stmt.order_by(LinkedAccount.confidence_score.desc())

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_all_linked_accounts(
    session: AsyncSession,
    status: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 100,
    offset: int = 0,
) -> List[LinkedAccount]:
    """Get all linked accounts with filtering"""
    stmt = (
        select(LinkedAccount)
        .where(LinkedAccount.confidence_score >= min_confidence)
        .order_by(LinkedAccount.confidence_score.desc(), LinkedAccount.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if status:
        stmt = stmt.where(LinkedAccount.status == status)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_linked_account_status(
    session: AsyncSession,
    link_id: int,
    status: str,
    admin_user_id: Optional[int] = None,
    admin_notes: Optional[str] = None,
) -> Optional[LinkedAccount]:
    """Update linked account status (admin action)"""
    stmt = select(LinkedAccount).where(LinkedAccount.id == link_id)
    result = await session.execute(stmt)
    link = result.scalar_one_or_none()

    if not link:
        return None

    link.status = status
    link.reviewed_at = datetime.now(UTC)
    link.reviewed_by = admin_user_id

    if admin_notes:
        link.admin_notes = admin_notes

    await session.commit()
    await session.refresh(link)

    logger.info(f"Updated linked account {link_id} status to {status} by admin {admin_user_id}")
    return link


# ===========================
# FRAUD DETECTION LOGIC
# ===========================


async def check_for_existing_trial(
    session: AsyncSession,
    ip_address: str,
    visitor_id: Optional[str] = None,
    fingerprint_hash: Optional[str] = None,
    exclude_user_id: Optional[int] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if any user with matching IP/fingerprint already had a trial

    Returns:
        Tuple of (has_existing_trial, evidence_dict)
    """
    matched_user_ids = set()
    evidence = {
        "ip_matches": [],
        "fingerprint_matches": [],
        "visitor_id_matches": [],
    }

    # Check IP matches
    if ip_address and ip_address not in IGNORED_IPS:
        ip_users = await get_users_by_ip(session, ip_address, exclude_user_id)
        matched_user_ids.update(ip_users)
        if ip_users:
            evidence["ip_matches"] = ip_users

    # Check visitor ID matches (FingerprintJS)
    if visitor_id:
        vid_users = await get_users_by_visitor_id(session, visitor_id, exclude_user_id)
        matched_user_ids.update(vid_users)
        if vid_users:
            evidence["visitor_id_matches"] = vid_users

    # Check fingerprint hash matches
    if fingerprint_hash:
        fp_users = await get_users_by_fingerprint_hash(session, fingerprint_hash, exclude_user_id)
        matched_user_ids.update(fp_users)
        if fp_users:
            evidence["fingerprint_matches"] = fp_users

    if not matched_user_ids:
        return False, None

    # Check if any matched user has/had a trial
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id.in_(matched_user_ids),
            Subscription.is_trial == True,
        )
    )
    result = await session.execute(stmt)
    trials = list(result.scalars().all())

    if trials:
        evidence["users_with_trial"] = [t.user_id for t in trials]
        logger.warning(
            f"Potential multi-trial abuse detected: "
            f"matched users={list(matched_user_ids)}, users_with_trial={evidence['users_with_trial']}"
        )
        return True, evidence

    return False, None


async def check_self_referral(
    session: AsyncSession,
    referrer_id: int,
    referee_ip: str,
    referee_visitor_id: Optional[str] = None,
    referee_fingerprint_hash: Optional[str] = None,
) -> Tuple[bool, float, Optional[Dict[str, Any]]]:
    """
    Check if referee is likely the same person as referrer (self-referral)

    Returns:
        Tuple of (is_self_referral, confidence_score, evidence_dict)
    """
    evidence = {
        "shared_ips": [],
        "shared_fingerprints": [],
        "shared_visitor_ids": [],
    }
    confidence = 0.0

    # Get referrer's fingerprints
    referrer_fps = await get_fingerprints_by_user(session, referrer_id)
    if not referrer_fps:
        return False, 0.0, None

    referrer_ips = {fp.ip_address for fp in referrer_fps if fp.ip_address not in IGNORED_IPS}
    referrer_visitor_ids = {fp.visitor_id for fp in referrer_fps if fp.visitor_id}
    referrer_hashes = {fp.fingerprint_hash for fp in referrer_fps if fp.fingerprint_hash}

    # Check IP match
    if referee_ip and referee_ip not in IGNORED_IPS and referee_ip in referrer_ips:
        evidence["shared_ips"].append(referee_ip)
        confidence += 0.4  # IP match = +40% confidence

    # Check visitor ID match (strongest signal)
    if referee_visitor_id and referee_visitor_id in referrer_visitor_ids:
        evidence["shared_visitor_ids"].append(referee_visitor_id)
        confidence += 0.5  # Visitor ID match = +50% confidence

    # Check fingerprint hash match
    if referee_fingerprint_hash and referee_fingerprint_hash in referrer_hashes:
        evidence["shared_fingerprints"].append(referee_fingerprint_hash)
        confidence += 0.4  # Fingerprint match = +40% confidence

    # Cap at 1.0
    confidence = min(confidence, 1.0)

    is_self_referral = confidence >= CONFIDENCE_MEDIUM

    if is_self_referral:
        logger.warning(
            f"Potential self-referral detected: referrer={referrer_id}, "
            f"confidence={confidence:.2f}, evidence={evidence}"
        )

    return is_self_referral, confidence, evidence if evidence["shared_ips"] or evidence["shared_visitor_ids"] or evidence["shared_fingerprints"] else None


async def detect_and_link_accounts(
    session: AsyncSession,
    user_id: int,
    ip_address: str,
    visitor_id: Optional[str] = None,
    fingerprint_hash: Optional[str] = None,
) -> List[LinkedAccount]:
    """
    Detect and create links to other accounts based on fingerprint/IP matches

    Called after registration or login to build the link graph
    """
    created_links = []

    # Find users with matching IP
    if ip_address and ip_address not in IGNORED_IPS:
        ip_matches = await get_users_by_ip(session, ip_address, user_id)
        for other_user_id in ip_matches:
            link = await create_or_update_linked_account(
                session,
                user_id_a=user_id,
                user_id_b=other_user_id,
                link_type=LinkedAccountType.IP_MATCH.value,
                confidence_score=CONFIDENCE_LOW,  # IP alone = low confidence
                shared_ips=[ip_address],
            )
            created_links.append(link)

    # Find users with matching visitor ID (high confidence)
    if visitor_id:
        vid_matches = await get_users_by_visitor_id(session, visitor_id, user_id)
        for other_user_id in vid_matches:
            link = await create_or_update_linked_account(
                session,
                user_id_a=user_id,
                user_id_b=other_user_id,
                link_type=LinkedAccountType.FINGERPRINT_MATCH.value,
                confidence_score=CONFIDENCE_HIGH,  # Visitor ID = high confidence
                shared_visitor_ids=[visitor_id],
            )
            created_links.append(link)

    # Find users with matching fingerprint hash
    if fingerprint_hash:
        fp_matches = await get_users_by_fingerprint_hash(session, fingerprint_hash, user_id)
        for other_user_id in fp_matches:
            link = await create_or_update_linked_account(
                session,
                user_id_a=user_id,
                user_id_b=other_user_id,
                link_type=LinkedAccountType.FINGERPRINT_MATCH.value,
                confidence_score=CONFIDENCE_MEDIUM,  # Custom hash = medium confidence
                shared_fingerprints=[fingerprint_hash],
            )
            created_links.append(link)

    return created_links


async def get_abuse_summary_for_admin(
    session: AsyncSession,
    days: int = 30,
) -> Dict[str, Any]:
    """Get summary of detected abuse for admin dashboard"""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Count by status
    stmt_status = (
        select(LinkedAccount.status, func.count(LinkedAccount.id))
        .where(LinkedAccount.created_at >= cutoff)
        .group_by(LinkedAccount.status)
    )
    result_status = await session.execute(stmt_status)
    status_counts = dict(result_status.all())

    # Count by type
    stmt_type = (
        select(LinkedAccount.link_type, func.count(LinkedAccount.id))
        .where(LinkedAccount.created_at >= cutoff)
        .group_by(LinkedAccount.link_type)
    )
    result_type = await session.execute(stmt_type)
    type_counts = dict(result_type.all())

    # High confidence links needing review
    stmt_pending = (
        select(func.count(LinkedAccount.id))
        .where(
            LinkedAccount.status == LinkedAccountStatus.DETECTED.value,
            LinkedAccount.confidence_score >= CONFIDENCE_MEDIUM,
            LinkedAccount.reviewed_at.is_(None),
        )
    )
    result_pending = await session.execute(stmt_pending)
    pending_review = result_pending.scalar() or 0

    return {
        "period_days": days,
        "status_counts": status_counts,
        "type_counts": type_counts,
        "pending_review_count": pending_review,
    }


# ===========================
# ADMIN ACTIONS
# ===========================


async def ban_linked_accounts(
    session: AsyncSession,
    link_id: int,
    admin_user_id: int,
    ban_both: bool = True,
) -> Dict[str, Any]:
    """
    Ban accounts based on linked account detection

    Args:
        link_id: LinkedAccount ID
        admin_user_id: Admin performing the action
        ban_both: If True, ban both accounts; if False, only the newer one
    """
    stmt = select(LinkedAccount).where(LinkedAccount.id == link_id)
    result = await session.execute(stmt)
    link = result.scalar_one_or_none()

    if not link:
        return {"success": False, "error": "Link not found"}

    # Get both users
    stmt_users = select(User).where(User.id.in_([link.user_id_a, link.user_id_b]))
    result_users = await session.execute(stmt_users)
    users = {u.id: u for u in result_users.scalars().all()}

    user_a = users.get(link.user_id_a)
    user_b = users.get(link.user_id_b)

    if not user_a or not user_b:
        return {"success": False, "error": "Users not found"}

    banned_users = []

    if ban_both:
        # Ban both
        user_a.is_banned = True
        user_b.is_banned = True
        banned_users = [user_a.id, user_b.id]
    else:
        # Ban only the newer account
        newer_user = user_a if user_a.created_at > user_b.created_at else user_b
        newer_user.is_banned = True
        banned_users = [newer_user.id]

    # Update link
    link.status = LinkedAccountStatus.CONFIRMED_ABUSE.value
    link.accounts_banned = True
    link.reviewed_at = datetime.now(UTC)
    link.reviewed_by = admin_user_id

    await session.commit()

    logger.info(f"Admin {admin_user_id} banned users {banned_users} based on link {link_id}")

    return {
        "success": True,
        "banned_users": banned_users,
        "link_id": link_id,
    }


async def get_linked_accounts_with_users(
    session: AsyncSession,
    status: Optional[str] = None,
    min_confidence: float = 0.5,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get linked accounts with full user info for admin panel"""
    links = await get_all_linked_accounts(session, status, min_confidence, limit)

    result = []
    for link in links:
        # Get both users
        stmt = select(User).where(User.id.in_([link.user_id_a, link.user_id_b])).options(
            selectinload(User.subscription)
        )
        users_result = await session.execute(stmt)
        users = {u.id: u for u in users_result.scalars().all()}

        user_a = users.get(link.user_id_a)
        user_b = users.get(link.user_id_b)

        result.append({
            "id": link.id,
            "link_type": link.link_type,
            "confidence_score": link.confidence_score,
            "status": link.status,
            "created_at": link.created_at.isoformat(),
            "reviewed_at": link.reviewed_at.isoformat() if link.reviewed_at else None,
            "shared_ips": json.loads(link.shared_ips or "[]"),
            "shared_fingerprints": json.loads(link.shared_fingerprints or "[]"),
            "shared_visitor_ids": json.loads(link.shared_visitor_ids or "[]"),
            "trial_blocked": link.trial_blocked,
            "referral_blocked": link.referral_blocked,
            "accounts_banned": link.accounts_banned,
            "admin_notes": link.admin_notes,
            "user_a": {
                "id": user_a.id if user_a else None,
                "telegram_id": user_a.telegram_id if user_a else None,
                "email": user_a.email if user_a else None,
                "username": user_a.username if user_a else None,
                "created_at": user_a.created_at.isoformat() if user_a else None,
                "is_banned": user_a.is_banned if user_a else None,
                "is_premium": user_a.is_premium if user_a else None,
                "registration_platform": user_a.registration_platform if user_a else None,
            } if user_a else None,
            "user_b": {
                "id": user_b.id if user_b else None,
                "telegram_id": user_b.telegram_id if user_b else None,
                "email": user_b.email if user_b else None,
                "username": user_b.username if user_b else None,
                "created_at": user_b.created_at.isoformat() if user_b else None,
                "is_banned": user_b.is_banned if user_b else None,
                "is_premium": user_b.is_premium if user_b else None,
                "registration_platform": user_b.registration_platform if user_b else None,
            } if user_b else None,
        })

    return result
