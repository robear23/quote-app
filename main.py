import os
import re
import secrets
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
from database import supabase
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_app = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global bot_app
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

def get_bot_username():
    if bot_app and bot_app.bot.username:
        return bot_app.bot.username
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
    try:
        response = httpx.get(url).json()
        if response.get("ok"):
            return response["result"]["username"]
    except Exception as e:
        logger.error(f"Failed to fetch bot username: {e}")
    return "YourBot"


def send_welcome_email(to_email: str, telegram_link: str):
    """Sends a welcome email with the Telegram deep-link via Resend."""
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
                    © 2026 Quote Me · Built for tradespeople, by Antigravity
                </p>
            </div>
            """,
        })
        logger.info(f"Welcome email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {to_email}: {e}")


def _upsert_user_by_email(email: str) -> dict:
    """Find or create a user by email. Returns the user row."""
    res = supabase.table("users").select("*").eq("email", email).execute()
    if res.data:
        return res.data[0]
    try:
        new = supabase.table("users").insert({"email": email, "bot_state": "HANDSHAKE"}).execute()
        return new.data[0]
    except Exception as e:
        err = str(e).lower()
        if "duplicate" in err or "unique" in err or "23505" in err:
            res2 = supabase.table("users").select("*").eq("email", email).execute()
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
def initiate_handshake(email: str):
    """
    Phase 1 web entry point (email-only flow, kept for backwards compatibility).
    Creates/fetches a user and returns the Telegram deep-link UUID.
    """
    email = email.strip().lower()
    if not email or not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Invalid email address")

    bot_username = get_bot_username()

    def _json_with_session(user_id: str, status: str) -> JSONResponse:
        res = JSONResponse({"user_id": user_id, "status": status, "bot_username": bot_username})
        _set_session_cookie(res, user_id)
        return res

    try:
        res = supabase.table("users").select("*").eq("email", email).execute()
        if res.data:
            user_id = res.data[0]["id"]
            return _json_with_session(user_id, "existing_user")

        try:
            new_user = supabase.table("users").insert({"email": email, "bot_state": "HANDSHAKE"}).execute()
            user_id = new_user.data[0]["id"]
            telegram_link = f"https://t.me/{bot_username}?start={user_id}"
            send_welcome_email(email, telegram_link)
            return _json_with_session(user_id, "new_user")
        except Exception as insert_err:
            err_str = str(insert_err).lower()
            if "duplicate" in err_str or "unique" in err_str or "23505" in err_str:
                retry = supabase.table("users").select("*").eq("email", email).execute()
                if retry.data:
                    return _json_with_session(retry.data[0]["id"], "existing_user")
            raise

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
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
        user = _upsert_user_by_email(email)
    except Exception as e:
        logger.error(f"User upsert failed after Google OAuth: {e}")
        return RedirectResponse("/?auth_error=db")

    # First-time login: send welcome email with Telegram link
    if not user.get("telegram_id"):
        bot_username = get_bot_username()
        telegram_link = f"https://t.me/{bot_username}?start={user['id']}"
        send_welcome_email(email, telegram_link)

    intent = request.cookies.get("oauth_intent", "")
    redirect_path = "/account?upgrade=1" if intent == "premium" else "/account"
    response = RedirectResponse(redirect_path)
    _set_session_cookie(response, user["id"])
    response.delete_cookie("oauth_state")
    response.delete_cookie("oauth_intent")
    return response


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
        user_res = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="User not found")
        user = user_res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    from subscription_service import get_user_tier, get_monthly_usage, monthly_limit_for_tier
    tier = await get_user_tier(user_id)
    usage = await get_monthly_usage(user_id)
    limit = monthly_limit_for_tier(tier)
    logger.info(f"Account API: user_id={user_id} email={user.get('email')} telegram_id={user.get('telegram_id')} usage={usage}/{limit}")

    bot_username = get_bot_username()
    telegram_url = f"https://t.me/{bot_username}?start={user_id}"

    # Subscription period end (if premium)
    period_end = None
    try:
        sub_res = supabase.table("subscriptions").select("current_period_end, status") \
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
        user_res = supabase.table("users").select("email, stripe_customer_id").eq("id", user_id).execute()
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
            supabase.table("users").update({"stripe_customer_id": customer_id}).eq("id", user_id).execute()
        except stripe.StripeError as e:
            logger.error(f"Stripe customer creation failed: {e}")
            raise HTTPException(status_code=502, detail="Payment provider error")

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": settings.STRIPE_PREMIUM_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.APP_URL}/billing/success",
            cancel_url=f"{settings.APP_URL}/account",
            metadata={"user_id": user_id},
        )
    except stripe.StripeError as e:
        logger.error(f"Stripe session creation failed: {e}")
        raise HTTPException(status_code=502, detail="Payment provider error")

    return {"checkout_url": session.url}


@app.get("/billing/success", response_class=HTMLResponse)
def billing_success():
    """Redirect page after successful Stripe checkout."""
    return RedirectResponse("/account?upgraded=1")


@app.get("/billing-portal")
async def billing_portal(request: Request):
    """Redirects the user to the Stripe Customer Portal to manage their subscription."""
    user_id = get_session_user_id(request)
    if not user_id:
        return RedirectResponse("/auth/google")

    try:
        user_res = supabase.table("users").select("stripe_customer_id").eq("id", user_id).execute()
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

    event_type = event["type"]
    logger.info(f"Stripe event received: {event_type}")

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(event["data"]["object"])

    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        await _handle_subscription_updated(event["data"]["object"])

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(event["data"]["object"])

    return {"ok": True}


async def _handle_checkout_completed(session: dict):
    """Promote user to premium after a successful checkout."""
    from subscription_service import upsert_subscription, get_user_by_stripe_customer

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    if not customer_id or not subscription_id:
        return

    user = await get_user_by_stripe_customer(customer_id)
    if not user:
        # Fallback: try metadata
        user_id = (session.get("metadata") or {}).get("user_id")
        if not user_id:
            logger.warning(f"Checkout completed but no user found for customer {customer_id}")
            return
    else:
        user_id = user["id"]

    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
        await upsert_subscription(
            user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan_tier="premium",
            status=sub["status"],
            current_period_end=period_end,
        )
        logger.info(f"User {user_id} upgraded to premium")
    except Exception as e:
        logger.error(f"Failed to upsert subscription after checkout: {e}")


async def _handle_subscription_updated(sub: dict):
    """Sync subscription status changes from Stripe."""
    from subscription_service import upsert_subscription, get_user_by_stripe_customer

    customer_id = sub.get("customer")
    user = await get_user_by_stripe_customer(customer_id)
    if not user:
        return

    status = sub.get("status", "canceled")
    tier = "premium" if status in ("active", "trialing") else "free"
    period_end = None
    if sub.get("current_period_end"):
        period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)

    await upsert_subscription(
        user_id=user["id"],
        stripe_customer_id=customer_id,
        stripe_subscription_id=sub["id"],
        plan_tier=tier,
        status=status,
        current_period_end=period_end,
    )
    logger.info(f"User {user['id']} subscription updated: {status} → tier={tier}")


async def _handle_subscription_deleted(sub: dict):
    """Downgrade user to free when subscription is cancelled."""
    from subscription_service import upsert_subscription, get_user_by_stripe_customer

    customer_id = sub.get("customer")
    user = await get_user_by_stripe_customer(customer_id)
    if not user:
        return

    await upsert_subscription(
        user_id=user["id"],
        stripe_customer_id=customer_id,
        stripe_subscription_id=sub["id"],
        plan_tier="free",
        status="canceled",
        current_period_end=None,
    )
    logger.info(f"User {user['id']} downgraded to free (subscription cancelled)")
