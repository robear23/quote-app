"""
Bot state machine for Quote Me.

All bot_state writes must go through the `transition()` coroutine so that:
- State constants are defined in one place (no scattered string literals)
- Invalid transitions surface as warnings rather than silent state corruption
- The write path is centralised and testable

State flow:
  HANDSHAKE
    → ONBOARDING (on first Telegram link)
  ONBOARDING
    → ONBOARDING_CURRENCY (template accepted)
    → ONBOARDING_REANALYSE (user requests field re-examine)
  ONBOARDING_REANALYSE
    → ONBOARDING
  ONBOARDING_CURRENCY
    → ONBOARDING_TAX
  ONBOARDING_TAX
    → AWAITING_CONFIG (collect validity period / custom field defaults)
    → ACTIVE
  AWAITING_FORMAT (legacy)
    → AWAITING_CONFIG
    → ACTIVE
  AWAITING_CONFIG
    → ACTIVE
  ACTIVE
    → AWAITING_CONFIRMATION (quote generated, awaiting send/discard)
    → AWAITING_CUSTOM_FIELD (collecting custom template fields)
    → ONBOARDING (user restarts onboarding via /restart)
  AWAITING_CUSTOM_FIELD
    → AWAITING_CONFIRMATION
    → ACTIVE
  AWAITING_CONFIRMATION
    → ACTIVE (quote sent, discarded, or generation failed)

Admin resets and the initial account-link write are exempt from transition
validation — they can write any valid state directly via _force_state().
"""

import logging

import database

logger = logging.getLogger(__name__)


class BotState:
    HANDSHAKE = "HANDSHAKE"
    ONBOARDING = "ONBOARDING"
    ONBOARDING_CURRENCY = "ONBOARDING_CURRENCY"
    ONBOARDING_TAX = "ONBOARDING_TAX"
    ONBOARDING_REANALYSE = "ONBOARDING_REANALYSE"
    AWAITING_FORMAT = "AWAITING_FORMAT"       # legacy — kept for existing rows
    AWAITING_CONFIG = "AWAITING_CONFIG"
    ACTIVE = "ACTIVE"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    AWAITING_CUSTOM_FIELD = "AWAITING_CUSTOM_FIELD"

    _ALL: frozenset[str] = frozenset()  # populated below


BotState._ALL = frozenset({
    BotState.HANDSHAKE,
    BotState.ONBOARDING,
    BotState.ONBOARDING_CURRENCY,
    BotState.ONBOARDING_TAX,
    BotState.ONBOARDING_REANALYSE,
    BotState.AWAITING_FORMAT,
    BotState.AWAITING_CONFIG,
    BotState.ACTIVE,
    BotState.AWAITING_CONFIRMATION,
    BotState.AWAITING_CUSTOM_FIELD,
})

# Allowed transitions: from_state → frozenset of valid to_states.
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    BotState.HANDSHAKE: frozenset({
        BotState.ONBOARDING,
    }),
    BotState.ONBOARDING: frozenset({
        BotState.ONBOARDING_CURRENCY,
        BotState.ONBOARDING_REANALYSE,
    }),
    BotState.ONBOARDING_REANALYSE: frozenset({
        BotState.ONBOARDING,
    }),
    BotState.ONBOARDING_CURRENCY: frozenset({
        BotState.ONBOARDING_TAX,
    }),
    BotState.ONBOARDING_TAX: frozenset({
        BotState.AWAITING_CONFIG,
        BotState.ACTIVE,
    }),
    BotState.AWAITING_FORMAT: frozenset({    # legacy
        BotState.AWAITING_CONFIG,
        BotState.ACTIVE,
    }),
    BotState.AWAITING_CONFIG: frozenset({
        BotState.ACTIVE,
    }),
    BotState.ACTIVE: frozenset({
        BotState.AWAITING_CONFIRMATION,
        BotState.AWAITING_CUSTOM_FIELD,
        BotState.ONBOARDING,
    }),
    BotState.AWAITING_CUSTOM_FIELD: frozenset({
        BotState.AWAITING_CONFIRMATION,
        BotState.ACTIVE,
    }),
    BotState.AWAITING_CONFIRMATION: frozenset({
        BotState.ACTIVE,
    }),
}


async def transition(telegram_id: int, new_state: str, current_state: str | None = None) -> None:
    """Write a new bot_state to Supabase, validating the transition when current_state is known.

    Invalid transitions are logged as warnings but not blocked — the bot must remain
    functional even if a user arrives in an unexpected state (e.g. after a manual reset).
    """
    if new_state not in BotState._ALL:
        logger.error(
            f"transition: unknown target state '{new_state}' for telegram_id={telegram_id}"
        )
        return

    if current_state is not None:
        allowed = VALID_TRANSITIONS.get(current_state, frozenset())
        if new_state not in allowed:
            logger.warning(
                f"Unexpected state transition for telegram_id={telegram_id}: "
                f"{current_state!r} → {new_state!r} "
                f"(not in allowed set {sorted(allowed)})"
            )

    await database.supabase.table("users") \
        .update({"bot_state": new_state}) \
        .eq("telegram_id", telegram_id) \
        .execute()


async def force_state(user_id: str, new_state: str) -> None:
    """Write bot_state directly by internal user UUID, bypassing transition validation.

    Use only for admin operations (resets, account linking) where the previous
    state is unknown or intentionally overridden.
    """
    if new_state not in BotState._ALL:
        logger.error(f"force_state: unknown target state '{new_state}' for user_id={user_id}")
        return
    await database.supabase.table("users") \
        .update({"bot_state": new_state}) \
        .eq("id", user_id) \
        .execute()
