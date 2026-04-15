"""
Subscription and usage helpers shared between main.py (web) and bot_manager.py (bot).
Uses the async Supabase client — all DB calls are native async (no asyncio.to_thread).
"""
import calendar
from datetime import datetime, timezone

import database

FREE_MONTHLY_LIMIT = 10
PREMIUM_MONTHLY_LIMIT = 100


async def get_user_tier(user_id: str) -> str:
    """
    Returns 'premium' if the user has an active subscription whose period
    has not yet ended, otherwise 'free'.
    """
    res = await database.supabase.table("subscriptions") \
        .select("plan_tier, status, current_period_end") \
        .eq("user_id", user_id) \
        .execute()
    sub = res.data[0] if res.data else None
    if not sub:
        return "free"

    if sub.get("plan_tier") != "premium":
        return "free"

    if sub.get("status") not in ("active", "trialing"):
        return "free"

    end_str = sub.get("current_period_end")
    if end_str:
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        if end_dt <= datetime.now(timezone.utc):
            return "free"

    return "premium"


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
