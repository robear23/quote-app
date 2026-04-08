"""
Subscription and usage helpers shared between main.py (web) and bot_manager.py (bot).
All DB calls are wrapped in asyncio.to_thread() to avoid blocking the event loop.
"""
import asyncio
from datetime import datetime, timezone

from database import supabase

FREE_MONTHLY_LIMIT = 10
PREMIUM_MONTHLY_LIMIT = 100


async def get_user_tier(user_id: str) -> str:
    """
    Returns 'premium' if the user has an active subscription whose period
    has not yet ended, otherwise 'free'.
    """
    def _fetch():
        res = supabase.table("subscriptions") \
            .select("plan_tier, status, current_period_end") \
            .eq("user_id", user_id) \
            .execute()
        return res.data[0] if res.data else None

    sub = await asyncio.to_thread(_fetch)
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


async def get_monthly_usage(user_id: str) -> int:
    """Returns the number of quotes generated this calendar month."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _count():
        res = supabase.table("documents") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .gte("created_at", month_start.isoformat()) \
            .execute()
        return res.count or 0

    return await asyncio.to_thread(_count)


def monthly_limit_for_tier(tier: str) -> int:
    return PREMIUM_MONTHLY_LIMIT if tier == "premium" else FREE_MONTHLY_LIMIT


async def upsert_subscription(
    user_id: str,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    plan_tier: str,
    status: str,
    current_period_end: datetime | None,
):
    """Create or update the subscriptions row for a user."""
    record = {
        "user_id": user_id,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        "plan_tier": plan_tier,
        "status": status,
        "current_period_end": current_period_end.isoformat() if current_period_end else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    def _upsert():
        supabase.table("subscriptions").upsert(record, on_conflict="user_id").execute()
        # Keep users.subscription_tier in sync for quick lookups
        supabase.table("users").update({"subscription_tier": plan_tier}) \
            .eq("id", user_id).execute()
        # Also store customer ID on the user row for easy webhook lookups
        supabase.table("users").update({"stripe_customer_id": stripe_customer_id}) \
            .eq("id", user_id).execute()

    await asyncio.to_thread(_upsert)


async def get_user_by_stripe_customer(stripe_customer_id: str) -> dict | None:
    """Look up a user by their Stripe customer ID (used in webhook handlers)."""
    def _fetch():
        res = supabase.table("users").select("*") \
            .eq("stripe_customer_id", stripe_customer_id).execute()
        return res.data[0] if res.data else None

    return await asyncio.to_thread(_fetch)
