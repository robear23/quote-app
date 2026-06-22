"""
Tests for subscription_service.billing_period_from_anchor.

These are pure unit tests — no DB or network required. The function is
deterministic given a fixed anchor timestamp and a fixed "now" value,
which is injected via the `_now` parameter added for testability.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from subscription_service import billing_period_from_anchor


def _dt(year, month, day, hour=0, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_standard_month_mid_period():
    """Anchor Jan 15. At Feb 20 the current period should be Jan 15 → Feb 15."""
    anchor = _dt(2026, 1, 15)
    now = _dt(2026, 2, 20)
    period_end, period_start = billing_period_from_anchor(int(anchor.timestamp()), _now=now)
    assert period_start == _dt(2026, 2, 15), f"Expected period_start=Feb 15, got {period_start}"
    assert period_end == _dt(2026, 3, 15), f"Expected period_end=Mar 15, got {period_end}"


def test_period_start_equals_anchor_day():
    """Anchor Mar 1. At Mar 10 the current period should be Mar 1 → Apr 1."""
    anchor = _dt(2026, 3, 1)
    now = _dt(2026, 3, 10)
    period_end, period_start = billing_period_from_anchor(int(anchor.timestamp()), _now=now)
    assert period_start == _dt(2026, 3, 1)
    assert period_end == _dt(2026, 4, 1)


def test_month_end_clamping():
    """Anchor Jan 31. Feb has only 28 days in 2026 — period_start must clamp to Feb 28."""
    anchor = _dt(2026, 1, 31)
    now = _dt(2026, 3, 5)
    period_end, period_start = billing_period_from_anchor(int(anchor.timestamp()), _now=now)
    # Feb 28 → Mar 28 (March has 31 days, so day 28 is safe)
    assert period_start == _dt(2026, 2, 28), f"Expected Feb 28, got {period_start}"
    assert period_end == _dt(2026, 3, 28), f"Expected Mar 28, got {period_end}"


def test_december_wraps_to_january():
    """Anchor Dec 15. At Jan 10 the current period should be Dec 15 → Jan 15."""
    anchor = _dt(2025, 12, 15)
    now = _dt(2026, 1, 10)
    period_end, period_start = billing_period_from_anchor(int(anchor.timestamp()), _now=now)
    assert period_start == _dt(2025, 12, 15)
    assert period_end == _dt(2026, 1, 15)


def test_period_end_is_in_the_future():
    """For any valid now, period_end must always be after now."""
    anchor = _dt(2026, 5, 10)
    for day in [11, 15, 20, 9]:   # before and after anchor day in same month
        now = _dt(2026, 6, day)
        period_end, period_start = billing_period_from_anchor(int(anchor.timestamp()), _now=now)
        assert period_end > now, f"period_end {period_end} should be after now={now}"
        assert period_start <= now, f"period_start {period_start} should be <= now={now}"


def test_period_start_before_period_end():
    """period_start must always be strictly before period_end."""
    anchor = _dt(2026, 4, 20)
    now = _dt(2026, 7, 1)
    period_end, period_start = billing_period_from_anchor(int(anchor.timestamp()), _now=now)
    assert period_start < period_end


if __name__ == "__main__":
    tests = [
        test_standard_month_mid_period,
        test_period_start_equals_anchor_day,
        test_month_end_clamping,
        test_december_wraps_to_january,
        test_period_end_is_in_the_future,
        test_period_start_before_period_end,
    ]
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
    print("Done.")
