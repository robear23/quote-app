"""
Entry point for cloud deployment.
The bot lifecycle (init, webhook setup, shutdown) is managed by FastAPI's lifespan in main.py.
"""
import asyncio
import os
import logging
import uvicorn

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main():
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config("main:app", host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
