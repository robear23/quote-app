import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Telegram Quote Agent"
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip().encode('ascii', 'ignore').decode('ascii')
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "").strip()
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@quoteagent.app").strip()
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "").strip()  # e.g. https://yourapp.railway.app
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "").strip()

settings = Settings()
