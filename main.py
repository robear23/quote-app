import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from database import supabase
import httpx
from config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Quote Agent API")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

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

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serve the sleek landing page."""
    with open("static/index.html", "r") as f:
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
        return {"user_id": user_id, "status": "new_user", "bot_username": bot_username}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error during handshake: {e}")
        return {"error": "Failed to initiate handshake"}

