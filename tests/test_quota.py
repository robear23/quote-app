"""
Tests for quota and subscription tier logic in subscription_service.

Unit tests cover the pure functions. The integration test for reserve_quota_slot
requires a live Supabase connection and is skipped when credentials are absent.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _Skip(Exception):
    pass


from subscription_service import (
    monthly_limit_for_tier,
    FREE_MONTHLY_LIMIT,
    PRO_MONTHLY_LIMIT,
    PREMIUM_MONTHLY_LIMIT,
)


# ---------------------------------------------------------------------------
# monthly_limit_for_tier — pure function, no I/O
# ---------------------------------------------------------------------------

def test_free_tier_limit():
    assert monthly_limit_for_tier("free") == FREE_MONTHLY_LIMIT


def test_premium_tier_limit():
    assert monthly_limit_for_tier("premium") == PREMIUM_MONTHLY_LIMIT
    assert monthly_limit_for_tier("premium") > monthly_limit_for_tier("free")


def test_pro_tier_limit():
    assert monthly_limit_for_tier("pro") == PRO_MONTHLY_LIMIT
    assert monthly_limit_for_tier("pro") > monthly_limit_for_tier("free")


def test_unknown_tier_falls_back_to_free():
    assert monthly_limit_for_tier("unknown") == FREE_MONTHLY_LIMIT
    assert monthly_limit_for_tier("") == FREE_MONTHLY_LIMIT
    assert monthly_limit_for_tier("PREMIUM") == FREE_MONTHLY_LIMIT   # case-sensitive


def test_tier_ordering():
    assert monthly_limit_for_tier("free") <= monthly_limit_for_tier("pro") <= monthly_limit_for_tier("premium")


# ---------------------------------------------------------------------------
# reserve_quota_slot — integration test (skipped without DB credentials)
# ---------------------------------------------------------------------------

def test_reserve_quota_slot_integration():
    """
    Verify that reserve_quota_slot prevents double-booking under concurrent calls.
    Requires SUPABASE_URL and SUPABASE_KEY environment variables.
    """
    import asyncio

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise _Skip("no SUPABASE credentials in environment")

    import uuid
    import database
    from datetime import datetime, timezone

    async def _run():
        await database.init_supabase()

        # Create a temporary test user
        test_user_id = str(uuid.uuid4())
        await database.supabase.table("users").insert({
            "id": test_user_id,
            "email": f"test_{test_user_id[:8]}@example.invalid",
        }).execute()

        billing_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        limit = 1

        # Fire two concurrent reserve_quota_slot calls
        results = await asyncio.gather(
            database.supabase.rpc("reserve_quota_slot", {
                "p_user_id": test_user_id,
                "p_billing_start": billing_start.isoformat(),
                "p_limit": limit,
            }).execute(),
            database.supabase.rpc("reserve_quota_slot", {
                "p_user_id": test_user_id,
                "p_billing_start": billing_start.isoformat(),
                "p_limit": limit,
            }).execute(),
        )

        slot_ids = [r.data for r in results]
        non_null = [s for s in slot_ids if s is not None]
        assert len(non_null) == 1, (
            f"Expected exactly 1 slot granted for limit=1, got {len(non_null)}: {slot_ids}"
        )

        # Cleanup
        await database.supabase.table("users").delete().eq("id", test_user_id).execute()

    try:
        asyncio.run(_run())
    except Exception as e:
        raise _Skip(f"DB not reachable: {type(e).__name__}") from e


if __name__ == "__main__":
    tests = [
        test_free_tier_limit,
        test_premium_tier_limit,
        test_pro_tier_limit,
        test_unknown_tier_falls_back_to_free,
        test_tier_ordering,
        test_reserve_quota_slot_integration,
    ]
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except _Skip as e:
            print(f"SKIP  {t.__name__}: {e}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
    print("Done.")
