import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Telegram Quote Me"
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip().encode('ascii', 'ignore').decode('ascii')
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "").strip()
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@quoteagent.app").strip()
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "").strip()  # e.g. https://yourapp.railway.app
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "").strip()

    # App base URL (used for OAuth redirect URIs and Stripe success/cancel URLs)
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000").strip().rstrip("/")

    # Google OAuth 2.0 — configure at console.cloud.google.com
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    # Stripe — configure at dashboard.stripe.com
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "").strip()
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    # Price ID for the £10/month Premium plan — create in Stripe dashboard
    STRIPE_PREMIUM_PRICE_ID: str = os.getenv("STRIPE_PREMIUM_PRICE_ID", "").strip()
    # Price ID for the £5/month Pro plan — create in Stripe dashboard
    STRIPE_PRO_PRICE_ID: str = os.getenv("STRIPE_PRO_PRICE_ID", "").strip()

    # Supabase Storage bucket for generated quote documents
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "documents")

    # Supabase Storage bucket for onboarding sample files (created separately in Supabase dashboard)
    SUPABASE_ONBOARDING_BUCKET: str = os.getenv("SUPABASE_ONBOARDING_BUCKET", "onboarding")

    # Supabase Storage bucket for per-user docxtpl quote templates
    SUPABASE_TEMPLATES_BUCKET: str = os.getenv("SUPABASE_TEMPLATES_BUCKET", "quote-templates")

    # Telegram chat ID for admin failure alerts — set to your own Telegram user ID
    ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID", "").strip()

    # Sentry error tracking — leave empty to disable
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "").strip()

    # Session signing secret — set a long random string in production
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "change-me-in-production").strip()

settings = Settings()
