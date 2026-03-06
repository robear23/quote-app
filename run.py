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
        async with bot_app:
            await bot_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            await bot_app.start()
            logger.info("Telegram bot started.")
            try:
                await server.serve()
            finally:
                await bot_app.updater.stop()
                await bot_app.stop()
    else:
        logger.warning("Bot not started — missing TELEGRAM_BOT_TOKEN. Running web server only.")
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
