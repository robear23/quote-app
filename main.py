import asyncio
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import resend
import stripe
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from telegram import Update

from config import settings
import database
from database import init_supabase
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_app = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global bot_app
    await init_supabase()
    from bot_manager import build_application
    bot_app = build_application()
    if bot_app:
        await bot_app.initialize()
        if settings.WEBHOOK_URL:
            webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}/telegram"
            kwargs = {"url": webhook_url, "drop_pending_updates": True}
            if settings.WEBHOOK_SECRET:
                kwargs["secret_token"] = settings.WEBHOOK_SECRET
            await bot_app.bot.set_webhook(**kwargs)
            logger.info(f"Webhook set to {webhook_url}")
        else:
            logger.warning("WEBHOOK_URL not set — bot will not receive updates")
        await bot_app.start()
    yield
    if bot_app:
        await bot_app.stop()
        await bot_app.shutdown()


app = FastAPI(title="Telegram Quote Me API", lifespan=lifespan)

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

# ---------------------------------------------------------------------------
# Magic-link token store (in-memory, single-use, 30-minute TTL)
# ---------------------------------------------------------------------------

# token -> (user_id, expires_at)
_login_tokens: dict[str, tuple[str, float]] = {}


def _generate_login_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _login_tokens[token] = (user_id, time.time() + 1800)
    return token


def _consume_login_token(token: str) -> str | None:
    """Returns user_id if token is valid and unexpired, then deletes it."""
    entry = _login_tokens.pop(token, None)
    if entry is None:
        return None
    user_id, expires_at = entry
    if time.time() > expires_at:
        return None
    return user_id


# ---------------------------------------------------------------------------
# Session helpers (signed cookie, 30-day expiry)
# ---------------------------------------------------------------------------

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SESSION_SECRET)


def make_session_token(user_id: str) -> str:
    return _serializer().dumps(user_id, salt="session")


def verify_session_token(token: str) -> str | None:
    try:
        return _serializer().loads(token, salt="session", max_age=86400 * 30)
    except (BadSignature, SignatureExpired):
        return None


def get_session_user_id(request: Request) -> str | None:
    token = request.cookies.get("qm_session")
    return verify_session_token(token) if token else None


def _set_session_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        "qm_session",
        make_session_token(user_id),
        max_age=86400 * 30,
        httponly=True,
        samesite="lax",
        secure=settings.APP_URL.startswith("https"),
    )


# ---------------------------------------------------------------------------
# Google OAuth helpers
# ---------------------------------------------------------------------------

def _google_oauth_url(state: str) -> str:
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": f"{settings.APP_URL}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"


async def _google_exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{settings.APP_URL}/auth/google/callback",
            },
        )
        tokens = token_res.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise ValueError(f"Google token exchange failed: {tokens}")

        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return user_res.json()


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

async def get_bot_username():
    if bot_app and bot_app.bot.username:
        return bot_app.bot.username
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
    try:
        response = await asyncio.to_thread(lambda: httpx.get(url).json())
        if response.get("ok"):
            return response["result"]["username"]
    except Exception as e:
        logger.error(f"Failed to fetch bot username: {e}")
    return "YourBot"


def send_magic_link_email(to_email: str, token: str, is_new_user: bool = False, telegram_link: str = None):
    """Sends a magic sign-in link. For new users, also includes the Telegram onboarding link."""
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — cannot send magic link.")
        return

    verify_url = f"{settings.APP_URL}/auth/email/verify?token={token}"

    if is_new_user and telegram_link:
        subject = "Welcome to Quote Me — tap to sign in"
        extra_html = f"""
                <hr style="border:none;border-top:1px solid #e2e8f0;margin:32px 0;">
                <p style="color:#64748b;font-size:0.85rem;margin-bottom:6px;"><strong>After signing in, open Telegram to get started:</strong></p>
                <a href="{telegram_link}"
                   style="display:inline-block;background:#229ED9;color:white;font-weight:600;
                          padding:12px 24px;border-radius:10px;text-decoration:none;font-size:0.95rem;margin-top:8px;">
                    Open Quote Me in Telegram
                </a>
                <ol style="color:#64748b;font-size:0.85rem;padding-left:20px;line-height:1.8;margin-top:20px;">
                    <li>Upload 3–10 past invoices or quotes so the AI can learn your style</li>
                    <li>Start generating branded quotes by voice, photo, or text</li>
                </ol>"""
        intro = "Your account is ready. Click the button below to sign in — the link expires in 30 minutes."
    else:
        subject = "Your Quote Me sign-in link"
        extra_html = ""
        intro = "Click the button below to sign in to Quote Me. This link expires in 30 minutes and can only be used once."

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": f"""
            <div style="font-family:Inter,sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;color:#1e293b;">
                <h1 style="font-size:1.6rem;font-weight:800;margin-bottom:8px;">Quote Me ⚡</h1>
                <p style="color:#475569;margin-bottom:24px;">{intro}</p>
                <a href="{verify_url}"
                   style="display:inline-block;background:#3b82f6;color:white;font-weight:600;
                          padding:14px 28px;border-radius:10px;text-decoration:none;font-size:1rem;">
                    Sign in to Quote Me
                </a>
                <p style="color:#94a3b8;font-size:0.78rem;margin-top:16px;">
                    If you didn't request this, you can safely ignore this email.
                </p>
                {extra_html}
                <p style="color:#94a3b8;font-size:0.78rem;margin-top:32px;">
                    © 2026 Quote Me · Built for tradespeople, by <a href="https://foresttechsolutions.net/" style="color:#94a3b8;text-decoration:underline;">ForestTech Solutions</a>
                </p>
            </div>
            """,
        })
        logger.info(f"Magic link email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send magic link to {to_email}: {e}")


def _send_google_welcome_email(to_email: str, telegram_link: str):
    """Sends a Telegram onboarding email to new users who signed up via Google OAuth."""
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping welcome email.")
        return
    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": "You're in — open Quote Me in Telegram",
            "html": f"""
            <div style="font-family:Inter,sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;color:#1e293b;">
                <h1 style="font-size:1.6rem;font-weight:800;margin-bottom:8px;">Welcome to Quote Me ⚡</h1>
                <p style="color:#475569;margin-bottom:24px;">
                    Your account is ready. Tap the button below to open Telegram and start training your AI — it only takes a few minutes.
                </p>
                <a href="{telegram_link}"
                   style="display:inline-block;background:#229ED9;color:white;font-weight:600;
                          padding:14px 28px;border-radius:10px;text-decoration:none;font-size:1rem;">
                    Open Quote Me in Telegram
                </a>
                <hr style="border:none;border-top:1px solid #e2e8f0;margin:32px 0;">
                <p style="color:#64748b;font-size:0.85rem;margin-bottom:6px;"><strong>What happens next:</strong></p>
                <ol style="color:#64748b;font-size:0.85rem;padding-left:20px;line-height:1.8;">
                    <li>Open the link above in Telegram</li>
                    <li>Upload 3–10 past invoices or quotes so the AI can learn your style</li>
                    <li>Start generating branded quotes by voice, photo, or text</li>
                </ol>
                <p style="color:#94a3b8;font-size:0.78rem;margin-top:32px;">
                    © 2026 Quote Me · Built for tradespeople, by <a href="https://foresttechsolutions.net/" style="color:#94a3b8;text-decoration:underline;">ForestTech Solutions</a>
                </p>
            </div>
            """,
        })
        logger.info(f"Google welcome email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send Google welcome email to {to_email}: {e}")


async def _upsert_user_by_email(email: str) -> dict:
    """Find or create a user by email. Returns the user row."""
    res = await database.supabase.table("users").select("*").eq("email", email).execute()
    if res.data:
        return res.data[0]
    try:
        new = await database.supabase.table("users").insert({"email": email, "bot_state": "HANDSHAKE"}).execute()
        return new.data[0]
    except Exception as e:
        err = str(e).lower()
        if "duplicate" in err or "unique" in err or "23505" in err:
            res2 = await database.supabase.table("users").select("*").eq("email", email).execute()
            if res2.data:
                return res2.data[0]
        raise


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/telegram")
async def telegram_webhook(request: Request):
    """Receives updates from Telegram and dispatches them to the bot."""
    if settings.WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != settings.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")
    if not bot_app:
        raise HTTPException(status_code=503, detail="Bot not ready")
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/account", response_class=HTMLResponse)
def account_page():
    with open("static/account.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/handshake")
async def initiate_handshake(email: str):
    """
    Email sign-in entry point. Sends a magic link — never grants a session directly.
    New users are created here; all users must click the emailed link to authenticate.
    """
    email = email.strip().lower()
    if not email or not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Invalid email address")

    if not settings.RESEND_API_KEY:
        raise HTTPException(status_code=503, detail="Email service not configured")

    bot_username = await get_bot_username()

    try:
        res = await database.supabase.table("users").select("id").eq("email", email).execute()

        if res.data:
            # Existing user: send magic link only — do NOT grant a session
            user_id = res.data[0]["id"]
            token = _generate_login_token(user_id)
            await asyncio.to_thread(send_magic_link_email, email, token, False)
        else:
            # New user: create account then send welcome + magic link
            try:
                new_user = await database.supabase.table("users").insert({"email": email, "bot_state": "HANDSHAKE"}).execute()
                user_id = new_user.data[0]["id"]
            except Exception as insert_err:
                err_str = str(insert_err).lower()
                if "duplicate" in err_str or "unique" in err_str or "23505" in err_str:
                    retry = await database.supabase.table("users").select("id").eq("email", email).execute()
                    if retry.data:
                        user_id = retry.data[0]["id"]
                        token = _generate_login_token(user_id)
                        await asyncio.to_thread(send_magic_link_email, email, token, False)
                        return JSONResponse({"status": "check_email"})
                raise
            telegram_link = f"https://t.me/{bot_username}?start={user_id}"
            token = _generate_login_token(user_id)
            await asyncio.to_thread(send_magic_link_email, email, token, True, telegram_link)

        return JSONResponse({"status": "check_email"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during handshake: {e}")
        return JSONResponse({"error": "Failed to initiate handshake"}, status_code=500)


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@app.get("/auth/google")
async def auth_google(intent: str = None):
    """Redirect user to Google's OAuth consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    state = secrets.token_urlsafe(16)
    redirect = RedirectResponse(_google_oauth_url(state))
    redirect.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite="lax")
    redirect.set_cookie("oauth_intent", intent or "", max_age=600, httponly=True, samesite="lax")
    return redirect


@app.get("/auth/google/callback")
async def auth_google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
):
    """Handle Google OAuth callback, create/link user, set session cookie."""
    if error or not code:
        return RedirectResponse("/?auth_error=1")

    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse("/?auth_error=csrf")

    try:
        user_info = await _google_exchange_code(code)
    except Exception as e:
        logger.error(f"Google code exchange failed: {e}")
        return RedirectResponse("/?auth_error=exchange")

    email = user_info.get("email")
    if not email:
        return RedirectResponse("/?auth_error=no_email")

    email = email.strip().lower()

    try:
        user = await _upsert_user_by_email(email)
    except Exception as e:
        logger.error(f"User upsert failed after Google OAuth: {e}")
        return RedirectResponse("/?auth_error=db")

    # First-time Google login: send welcome email with Telegram link
    if not user.get("telegram_id"):
        bot_username = await get_bot_username()
        telegram_link = f"https://t.me/{bot_username}?start={user['id']}"
        await asyncio.to_thread(_send_google_welcome_email, email, telegram_link)

    intent = request.cookies.get("oauth_intent", "")
    redirect_path = "/account?upgrade=1" if intent == "premium" else "/account"
    response = RedirectResponse(redirect_path)
    _set_session_cookie(response, user["id"])
    response.delete_cookie("oauth_state")
    response.delete_cookie("oauth_intent")
    return response


@app.get("/auth/email/verify")
async def auth_email_verify(token: str):
    """Validates a magic link token and creates a session."""
    user_id = _consume_login_token(token)
    if not user_id:
        return RedirectResponse("/?auth_error=invalid_link")
    redirect = RedirectResponse("/account")
    _set_session_cookie(redirect, user_id)
    return redirect


@app.post("/auth/logout")
async def auth_logout():
    redirect = RedirectResponse("/", status_code=303)
    redirect.delete_cookie("qm_session")
    return redirect


# ---------------------------------------------------------------------------
# Account API (requires session)
# ---------------------------------------------------------------------------

@app.get("/api/account")
async def api_account(request: Request):
    """Returns the current user's account info as JSON."""
    user_id = get_session_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_res = await database.supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="User not found")
        user = user_res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    from subscription_service import get_user_tier, get_monthly_usage, monthly_limit_for_tier, get_billing_period_start
    tier = await get_user_tier(user_id)
    usage = await get_monthly_usage(user_id)
    limit = monthly_limit_for_tier(tier)
    period_start = await get_billing_period_start(user_id)
    logger.info(f"Account API: user_id={user_id} email={user.get('email')} telegram_id={user.get('telegram_id')} usage={usage}/{limit}")

    bot_username = await get_bot_username()
    telegram_url = f"https://t.me/{bot_username}?start={user_id}"

    # Subscription period end (if premium)
    period_end = None
    try:
        sub_res = await database.supabase.table("subscriptions").select("current_period_end, status") \
            .eq("user_id", user_id).execute()
        if sub_res.data:
            period_end = sub_res.data[0].get("current_period_end")
    except Exception:
        pass

    return {
        "user_id": user_id,
        "email": user.get("email"),
        "subscription_tier": tier,
        "monthly_usage": usage,
        "monthly_limit": limit,
        "telegram_linked": bool(user.get("telegram_id")),
        "telegram_id": user.get("telegram_id"),
        "telegram_url": telegram_url,
        "bot_username": bot_username,
        "subscription_period_end": period_end,
        "billing_period_start": period_start.isoformat(),
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }


# ---------------------------------------------------------------------------
# Stripe checkout & billing portal
# ---------------------------------------------------------------------------

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    """Creates a Stripe Checkout session for the Premium subscription."""
    user_id = get_session_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PREMIUM_PRICE_ID:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    try:
        user_res = await database.supabase.table("users").select("email, stripe_customer_id").eq("id", user_id).execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="User not found")
        user = user_res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB error in checkout: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    # Reuse existing Stripe customer or create one
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        try:
            customer = stripe.Customer.create(email=user["email"], metadata={"user_id": user_id})
            customer_id = customer.id
            await database.supabase.table("users").update({"stripe_customer_id": customer_id}).eq("id", user_id).execute()
        except stripe.StripeError as e:
            logger.error(f"Stripe customer creation failed: {e}")
            raise HTTPException(status_code=502, detail="Payment provider error")

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": settings.STRIPE_PREMIUM_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.APP_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.APP_URL}/account",
            metadata={"user_id": user_id},
        )
    except stripe.StripeError as e:
        logger.error(f"Stripe session creation failed: {e}")
        raise HTTPException(status_code=502, detail="Payment provider error")

    return {"checkout_url": session.url}


@app.get("/billing/success")
async def billing_success(session_id: str = None):
    """Proactively sync subscription after successful Stripe checkout, then redirect."""
    if session_id and settings.STRIPE_SECRET_KEY:
        try:
            session = await asyncio.to_thread(
                stripe.checkout.Session.retrieve, session_id
            )
            await _handle_checkout_completed(session)
        except Exception as e:
            logger.error(f"Failed to sync subscription on billing success: {e}")
    return RedirectResponse("/account?upgraded=1")


@app.get("/billing-portal")
async def billing_portal(request: Request):
    """Redirects the user to the Stripe Customer Portal to manage their subscription."""
    user_id = get_session_user_id(request)
    if not user_id:
        return RedirectResponse("/auth/google")

    try:
        user_res = await database.supabase.table("users").select("stripe_customer_id").eq("id", user_id).execute()
        customer_id = user_res.data[0].get("stripe_customer_id") if user_res.data else None
    except Exception:
        customer_id = None

    if not customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    try:
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{settings.APP_URL}/account",
        )
        return RedirectResponse(portal.url)
    except stripe.StripeError as e:
        logger.error(f"Stripe portal error: {e}")
        raise HTTPException(status_code=502, detail="Payment provider error")


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handles Stripe subscription lifecycle events."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhook not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Stripe webhook construct_event failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Webhook parse error")

    event_type = event["type"]
    logger.info(f"Stripe event received: {event_type}")

    try:
        data_obj = event["data"]["object"]
    except Exception:
        data_obj = event.data.object

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data_obj)

    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        await _handle_subscription_updated(data_obj)

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data_obj)

    return {"ok": True}


def _get(obj, key, default=None):
    """Safe getter that works on both Stripe SDK objects and plain dicts."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


async def _handle_checkout_completed(session):
    """Promote user to premium after a successful checkout."""
    from subscription_service import upsert_subscription, get_user_by_stripe_customer

    try:
        customer_id = _get(session, "customer")
        subscription_id = _get(session, "subscription")
        if not customer_id or not subscription_id:
            logger.warning(f"checkout.session.completed missing customer/subscription: customer={customer_id} sub={subscription_id}")
            return

        user = await get_user_by_stripe_customer(customer_id)
        if not user:
            # Fallback: try metadata
            metadata = _get(session, "metadata")
            user_id = metadata.get("user_id") if isinstance(metadata, dict) else _get(metadata, "user_id")
            if not user_id:
                logger.warning(f"Checkout completed but no user found for customer {customer_id}")
                return
        else:
            user_id = user["id"]

        sub = await asyncio.to_thread(stripe.Subscription.retrieve, subscription_id)
        period_end = datetime.fromtimestamp(_get(sub, "current_period_end"), tz=timezone.utc)
        period_start = datetime.fromtimestamp(_get(sub, "current_period_start"), tz=timezone.utc)
        await upsert_subscription(
            user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan_tier="premium",
            status=_get(sub, "status"),
            current_period_end=period_end,
            current_period_start=period_start,
        )
        logger.info(f"User {user_id} upgraded to premium")
    except Exception as e:
        logger.error(f"_handle_checkout_completed failed: {e}", exc_info=True)


async def _handle_subscription_updated(sub):
    """Sync subscription status changes from Stripe."""
    from subscription_service import upsert_subscription, get_user_by_stripe_customer

    try:
        customer_id = _get(sub, "customer")
        user = await get_user_by_stripe_customer(customer_id)
        if not user:
            return

        status = _get(sub, "status") or "canceled"
        tier = "premium" if status in ("active", "trialing") else "free"
        period_end = None
        period_start = None
        period_end_ts = _get(sub, "current_period_end")
        period_start_ts = _get(sub, "current_period_start")
        if period_end_ts:
            period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)
        if period_start_ts:
            period_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc)

        await upsert_subscription(
            user_id=user["id"],
            stripe_customer_id=customer_id,
            stripe_subscription_id=_get(sub, "id"),
            plan_tier=tier,
            status=status,
            current_period_end=period_end,
            current_period_start=period_start,
        )
        logger.info(f"User {user['id']} subscription updated: {status} → tier={tier}")
    except Exception as e:
        logger.error(f"_handle_subscription_updated failed: {e}", exc_info=True)


async def _handle_subscription_deleted(sub):
    """Downgrade user to free when subscription is cancelled."""
    from subscription_service import upsert_subscription, get_user_by_stripe_customer

    try:
        customer_id = _get(sub, "customer")
        user = await get_user_by_stripe_customer(customer_id)
        if not user:
            return

        await upsert_subscription(
            user_id=user["id"],
            stripe_customer_id=customer_id,
            stripe_subscription_id=_get(sub, "id"),
            plan_tier="free",
            status="canceled",
            current_period_end=None,
        )
        logger.info(f"User {user['id']} downgraded to free (subscription cancelled)")
    except Exception as e:
        logger.error(f"_handle_subscription_deleted failed: {e}", exc_info=True)
