"""
Subscription and usage helpers shared between main.py (web) and bot_manager.py (bot).
Uses the async Supabase client — all DB calls are native async (no asyncio.to_thread).
"""
import calendar
from datetime import datetime, timedelta, timezone

import database

FREE_MONTHLY_LIMIT = 5
PREMIUM_MONTHLY_LIMIT = 100


async def get_user_tier(user_id: str) -> str:
    """
    Returns 'premium' if the user has an active Stripe subscription or an active
    premium_months promo redemption, otherwise 'free'.
    """
    now = datetime.now(timezone.utc)

    # Check Stripe subscription
    res = await database.supabase.table("subscriptions") \
        .select("plan_tier, status, current_period_end") \
        .eq("user_id", user_id) \
        .execute()
    sub = res.data[0] if res.data else None
    if sub and sub.get("plan_tier") == "premium" and sub.get("status") in ("active", "trialing"):
        end_str = sub.get("current_period_end")
        if not end_str or datetime.fromisoformat(end_str.replace("Z", "+00:00")) > now:
            return "premium"

    # Check active premium_months promo
    promo_res = await database.supabase.table("user_promo_redemptions") \
        .select("expires_at") \
        .eq("user_id", user_id) \
        .eq("benefit_type", "premium_months") \
        .gt("expires_at", now.isoformat()) \
        .execute()
    if promo_res.data:
        return "premium"

    return "free"


async def get_active_extra_quotes_limit(user_id: str) -> int | None:
    """
    Returns the quote limit from an active extra_quotes promo, or None if none active.
    """
    now = datetime.now(timezone.utc)
    res = await database.supabase.table("user_promo_redemptions") \
        .select("benefit_value") \
        .eq("user_id", user_id) \
        .eq("benefit_type", "extra_quotes") \
        .gt("expires_at", now.isoformat()) \
        .execute()
    if res.data:
        return max(row["benefit_value"] for row in res.data)
    return None


async def redeem_promo_code(user_id: str, code: str) -> dict:
    """
    Validates and redeems a promo code for a user.
    Returns {"success": True, "message": "..."} or {"success": False, "error": "..."}.
    """
    now = datetime.now(timezone.utc)
    code = code.strip().lower()

    # Fetch the code
    code_res = await database.supabase.table("promo_codes") \
        .select("*") \
        .eq("code", code) \
        .execute()
    if not code_res.data:
        return {"success": False, "error": "That code doesn't exist. Check for typos and try again."}

    promo = code_res.data[0]

    if not promo.get("is_active"):
        return {"success": False, "error": "That code is no longer active."}

    if promo.get("expires_at"):
        exp = datetime.fromisoformat(promo["expires_at"].replace("Z", "+00:00"))
        if exp <= now:
            return {"success": False, "error": "That code has expired."}

    max_uses = promo.get("max_uses")
    if max_uses is not None and promo.get("uses_count", 0) >= max_uses:
        return {"success": False, "error": "That code has reached its maximum number of uses."}

    # Check if user already redeemed it
    existing = await database.supabase.table("user_promo_redemptions") \
        .select("id") \
        .eq("user_id", user_id) \
        .eq("code", code) \
        .execute()
    if existing.data:
        return {"success": False, "error": "You've already redeemed that code."}

    # Calculate expiry
    benefit_type = promo["benefit_type"]
    benefit_value = promo["benefit_value"]
    if benefit_type == "extra_quotes":
        expires_at = now + timedelta(days=30)
        description = f"{benefit_value} quotes/month for 30 days"
    elif benefit_type == "premium_months":
        # Add N calendar months
        month = now.month + benefit_value
        year = now.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        max_day = calendar.monthrange(year, month)[1]
        expires_at = now.replace(year=year, month=month, day=min(now.day, max_day))
        description = f"full premium access for {benefit_value} month{'s' if benefit_value != 1 else ''}"
    else:
        return {"success": False, "error": "Unknown benefit type."}

    # Insert redemption
    await database.supabase.table("user_promo_redemptions").insert({
        "user_id": user_id,
        "code": code,
        "expires_at": expires_at.isoformat(),
        "benefit_type": benefit_type,
        "benefit_value": benefit_value,
    }).execute()

    # Increment uses_count
    await database.supabase.table("promo_codes") \
        .update({"uses_count": promo.get("uses_count", 0) + 1}) \
        .eq("code", code) \
        .execute()

    expires_str = expires_at.strftime("%-d %B %Y")
    return {
        "success": True,
        "message": f"Code applied! You now have {description} until {expires_str}.",
    }


def _subtract_one_month(dt: datetime) -> datetime:
    """Subtract one calendar month, clamping to the last day of the target month."""
    month = dt.month - 1
    year = dt.year
    if month == 0:
        month = 12
        year -= 1
    max_day = calendar.monthrange(year, month)[1]
    return dt.replace(year=year, month=month, day=min(dt.day, max_day))


async def get_billing_period_start(user_id: str) -> datetime:
    """
    Returns the start of the current billing period for usage counting.
    Premium users: uses stored current_period_start, or falls back to
    current_period_end minus one month.
    Free users: returns the 1st of the current calendar month.
    """
    now = datetime.now(timezone.utc)
    res = await database.supabase.table("subscriptions") \
        .select("plan_tier, status, current_period_start, current_period_end") \
        .eq("user_id", user_id) \
        .execute()
    sub = res.data[0] if res.data else None

    if sub and sub.get("plan_tier") == "premium" and sub.get("status") in ("active", "trialing"):
        start_str = sub.get("current_period_start")
        if start_str:
            return datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end_str = sub.get("current_period_end")
        if end_str:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            return _subtract_one_month(end_dt)

    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def get_monthly_usage(user_id: str) -> int:
    """Returns the number of quotes generated in the current billing period."""
    period_start = await get_billing_period_start(user_id)
    res = await database.supabase.table("documents") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .gte("created_at", period_start.isoformat()) \
        .execute()
    return res.count or 0


def monthly_limit_for_tier(tier: str) -> int:
    return PREMIUM_MONTHLY_LIMIT if tier == "premium" else FREE_MONTHLY_LIMIT


async def upsert_subscription(
    user_id: str,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    plan_tier: str,
    status: str,
    current_period_end: datetime | None,
    current_period_start: datetime | None = None,
):
    """Create or update the subscriptions row for a user."""
    record = {
        "user_id": user_id,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        "plan_tier": plan_tier,
        "status": status,
        "current_period_end": current_period_end.isoformat() if current_period_end else None,
        "current_period_start": current_period_start.isoformat() if current_period_start else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await database.supabase.table("subscriptions").upsert(record, on_conflict="user_id").execute()
    # Keep users.subscription_tier in sync for quick lookups
    await database.supabase.table("users").update({"subscription_tier": plan_tier}) \
        .eq("id", user_id).execute()
    # Also store customer ID on the user row for easy webhook lookups
    await database.supabase.table("users").update({"stripe_customer_id": stripe_customer_id}) \
        .eq("id", user_id).execute()


async def get_user_by_stripe_customer(stripe_customer_id: str) -> dict | None:
    """Look up a user by their Stripe customer ID (used in webhook handlers)."""
    res = await database.supabase.table("users").select("*") \
        .eq("stripe_customer_id", stripe_customer_id).execute()
    return res.data[0] if res.data else None
