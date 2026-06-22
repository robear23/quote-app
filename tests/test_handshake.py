"""
Tests for the handshake rate-limit logic introduced in Phase 3A.

The rate limit is enforced by a Supabase RPC (`check_handshake_rate_limit`).
These tests mock the DB call to verify the Python-side behaviour:
  - allowed when RPC returns truthy
  - blocked when RPC returns falsy
  - fails open (allows) when the RPC raises an exception (DB transient failure)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers to build a fake supabase chain: .rpc(...).execute()
# ---------------------------------------------------------------------------

def _mock_rpc_result(return_value):
    """Returns a mock supabase client whose .rpc(...).execute() resolves to return_value."""
    execute_mock = AsyncMock(return_value=MagicMock(data=return_value))
    rpc_mock = MagicMock()
    rpc_mock.return_value.execute = execute_mock
    client = MagicMock()
    client.rpc = rpc_mock
    return client


def _mock_rpc_raises(exc):
    """Returns a mock supabase client whose .rpc(...).execute() raises exc."""
    async def _raise():
        raise exc
    execute_mock = AsyncMock(side_effect=exc)
    rpc_mock = MagicMock()
    rpc_mock.return_value.execute = execute_mock
    client = MagicMock()
    client.rpc = rpc_mock
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_allowed_when_rpc_returns_true():
    """RPC returns True → the caller receives True (request is allowed)."""
    import database as _db_module

    async def _run():
        with patch.object(_db_module, "supabase", _mock_rpc_result(True)):
            # Import here to avoid top-level main.py side-effects
            from main import _check_and_record_handshake  # noqa: PLC0415
            result = await _check_and_record_handshake("user@example.com")
        return result

    result = asyncio.run(_run())
    assert result is True, f"Expected True, got {result}"


def test_blocked_when_rpc_returns_false():
    """RPC returns False → the caller receives False (request is rate-limited)."""
    import database as _db_module

    async def _run():
        with patch.object(_db_module, "supabase", _mock_rpc_result(False)):
            from main import _check_and_record_handshake  # noqa: PLC0415
            result = await _check_and_record_handshake("user@example.com")
        return result

    result = asyncio.run(_run())
    assert result is False, f"Expected False, got {result}"


def test_fails_open_on_rpc_exception():
    """If the RPC raises (DB transient error), the function fails open and returns True.

    A legitimate user must never be blocked by a database hiccup.
    """
    import database as _db_module

    async def _run():
        with patch.object(_db_module, "supabase", _mock_rpc_raises(RuntimeError("connection refused"))):
            from main import _check_and_record_handshake  # noqa: PLC0415
            result = await _check_and_record_handshake("user@example.com")
        return result

    result = asyncio.run(_run())
    assert result is True, f"Expected True (fail-open), got {result}"


def test_rpc_called_with_correct_email():
    """Verify the RPC is called with the exact email passed by the caller."""
    import database as _db_module

    target_email = "specific@example.com"
    client = _mock_rpc_result(True)

    async def _run():
        with patch.object(_db_module, "supabase", client):
            from main import _check_and_record_handshake  # noqa: PLC0415
            await _check_and_record_handshake(target_email)

    asyncio.run(_run())
    client.rpc.assert_called_once_with(
        "check_handshake_rate_limit", {"p_email": target_email}
    )


if __name__ == "__main__":
    tests = [
        test_allowed_when_rpc_returns_true,
        test_blocked_when_rpc_returns_false,
        test_fails_open_on_rpc_exception,
        test_rpc_called_with_correct_email,
    ]
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print("Done.")
