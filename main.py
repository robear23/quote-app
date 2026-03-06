import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from database import supabase
import httpx
import resend
from config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Quote Agent API")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY

bot_username_cache = None

def get_bot_username():
    global bot_username_cache
    if bot_username_cache: return bot_username_cache
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
    try:
        response = httpx.get(url).json()
        if response.get("ok"):
            bot_username_cache = response["result"]["username"]
            return bot_username_cache
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
            "subject": "You're in — open Quote Agent in Telegram",
            "html": f"""
            <div style="font-family:Inter,sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;color:#1e293b;">
                <h1 style="font-size:1.6rem;font-weight:800;margin-bottom:8px;">Welcome to Quote Agent ⚡</h1>
                <p style="color:#475569;margin-bottom:24px;">
                    Your account is ready. Tap the button below to open Telegram and start training your AI — it only takes a few minutes.
                </p>
                <a href="{telegram_link}"
                   style="display:inline-block;background:#229ED9;color:white;font-weight:600;
                          padding:14px 28px;border-radius:10px;text-decoration:none;font-size:1rem;">
                    Open Quote Agent in Telegram
                </a>
                <hr style="border:none;border-top:1px solid #e2e8f0;margin:32px 0;">
                <p style="color:#64748b;font-size:0.85rem;margin-bottom:6px;"><strong>What happens next:</strong></p>
                <ol style="color:#64748b;font-size:0.85rem;padding-left:20px;line-height:1.8;">
                    <li>Open the link above in Telegram</li>
                    <li>Upload 3–10 past invoices or quotes so the AI can learn your style</li>
                    <li>Start generating branded quotes by voice, photo, or text</li>
                </ol>
                <p style="color:#94a3b8;font-size:0.78rem;margin-top:32px;">
                    © 2026 Quote Agent · Built for tradespeople, by Antigravity
                </p>
            </div>
            """,
        })
        logger.info(f"Welcome email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {to_email}: {e}")


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
    bot_username = get_bot_username()
    
    try:
        # Basic check if user exists
        response = supabase.table("users").select("*").eq("email", email).execute()
        
        if response.data:
            user_id = response.data[0]['id']
            logger.info(f"User {email} already exists. Redirecting with ID: {user_id}")
            return {"user_id": user_id, "status": "existing_user", "bot_username": bot_username}
            
        # Create new user
        new_user = supabase.table("users").insert({"email": email, "bot_state": "HANDSHAKE"}).execute()
        user_id = new_user.data[0]['id']
        logger.info(f"Created new user {email} with ID: {user_id}")
        telegram_link = f"https://t.me/{bot_username}?start={user_id}"
        send_welcome_email(email, telegram_link)
        return {"user_id": user_id, "status": "new_user", "bot_username": bot_username}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error during handshake: {e}")
        return {"error": "Failed to initiate handshake"}

