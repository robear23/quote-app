import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from database import supabase
import httpx
import resend
from config import settings
from telegram import Update
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
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

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

def get_bot_username():
    if bot_app and bot_app.bot.username:
        return bot_app.bot.username
    # Fallback before bot is initialized
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


@app.get("/health")
def health_check():
    """Health check endpoint for load balancers and monitoring."""
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
    """Serve the sleek landing page."""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/handshake")
def initiate_handshake(email: str):
    """
    Phase 1: Web Entry point.
    Creates a user record with the 'HANDSHAKE' state and returns the UUID.
    The web client uses this UUID to deep-link to the Telegram Bot.
    """
    email = email.strip().lower()
    if not email or not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Invalid email address")

    bot_username = get_bot_username()

    try:
        # Check if user already exists
        response = supabase.table("users").select("*").eq("email", email).execute()

        if response.data:
            user_id = response.data[0]['id']
            logger.info(f"User {email} already exists. Redirecting with ID: {user_id}")
            return {"user_id": user_id, "status": "existing_user", "bot_username": bot_username}

        # Create new user — inner try/except handles duplicate race condition
        try:
            new_user = supabase.table("users").insert({"email": email, "bot_state": "HANDSHAKE"}).execute()
            user_id = new_user.data[0]['id']
            logger.info(f"Created new user {email} with ID: {user_id}")
            telegram_link = f"https://t.me/{bot_username}?start={user_id}"
            send_welcome_email(email, telegram_link)
            return {"user_id": user_id, "status": "new_user", "bot_username": bot_username}
        except Exception as insert_err:
            err_str = str(insert_err).lower()
            if "duplicate" in err_str or "unique" in err_str or "23505" in err_str:
                # Concurrent request just created this user — fetch and return it
                retry = supabase.table("users").select("*").eq("email", email).execute()
                if retry.data:
                    user_id = retry.data[0]['id']
                    return {"user_id": user_id, "status": "existing_user", "bot_username": bot_username}
            raise

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error during handshake: {e}")
        return {"error": "Failed to initiate handshake"}
