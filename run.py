"""
Combined entry point for cloud deployment.
Runs both the FastAPI web server and the Telegram bot in a single asyncio event loop.
"""
import asyncio
import os
import logging
import uvicorn
from telegram import Update

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def main():
    from bot_manager import build_application

    port = int(os.environ.get("PORT", 8000))

    # Build bot
    bot_app = build_application()

    # Configure uvicorn to run as a coroutine
    config = uvicorn.Config("main:app", host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    if bot_app:
        async def run_bot():
            try:
                async with bot_app:
                    await bot_app.updater.start_polling(
                        allowed_updates=Update.ALL_TYPES,
                        drop_pending_updates=True
                    )
                    await bot_app.start()
                    logger.info("Telegram bot started.")
                    # Wait until the web server signals exit
                    while not server.should_exit:
                        await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Bot encountered a fatal error: {e}", exc_info=True)

        await asyncio.gather(server.serve(), run_bot())
    else:
        logger.warning("Bot not started — missing TELEGRAM_BOT_TOKEN. Running web server only.")
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
