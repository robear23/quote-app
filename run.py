"""
Combined entry point for cloud deployment.
Runs both the FastAPI web server and the Telegram bot in a single process.
"""
import threading
import uvicorn
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def start_bot():
    """Runs the Telegram bot polling in a background thread."""
    from bot_manager import run_bot
    logger.info("Starting Telegram bot polling in background thread...")
    run_bot()


def start_web():
    """Runs the FastAPI web server."""
    import os
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting FastAPI web server on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    # Start bot in a daemon thread so it doesn't block the web server
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    # Start web server in main thread (blocking)
    start_web()
