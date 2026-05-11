from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    APP_NAME: str = "Malaysia AI Social Monitor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # API
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://yourdomain.com"]

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "change-this-in-production-use-secrets-manager"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Monitoring / NLP thresholds
    NARRATIVE_SIMILARITY_THRESHOLD: float = 0.82
    EMERGING_SPIKE_MULTIPLIER: float = 3.0
    ALERT_RATE_WINDOW_HOURS: int = 1
    MAX_NARRATIVE_CLUSTERS: int = 50
    EMBEDDING_BATCH_SIZE: int = 100
    RATE_LIMIT_PER_MINUTE: int = 120

    # ── Twitter / X ──────────────────────────────────────────────────────────
    # Bearer Token for app-only authentication (Twitter API v2).
    # Required for the Recent Search endpoint.
    # Get it from: https://developer.twitter.com/en/portal/dashboard
    TWITTER_BEARER_TOKEN: str = ""

    # ── Facebook ─────────────────────────────────────────────────────────────
    # Long-lived Page Access Token or System User token.
    # Must have: pages_read_engagement, pages_show_list
    # Generate via: https://developers.facebook.com/tools/explorer/
    FACEBOOK_ACCESS_TOKEN: str = ""
    FACEBOOK_APP_ID: str = ""
    # JSON array of extra pages beyond the built-in list:
    # e.g. '[{"id": "somepage", "name": "Some Page"}]'
    FACEBOOK_EXTRA_PAGES: str = "[]"

    # ── TikTok Research API ───────────────────────────────────────────────────
    # Requires an approved TikTok Research API application.
    # Apply at: https://developers.tiktok.com/products/research-api/
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""

    # ── RSS ───────────────────────────────────────────────────────────────────
    # Optional extra feeds beyond the built-in list.
    # JSON array: '[{"url": "https://...", "source": "My Feed"}]'
    RSS_EXTRA_FEEDS: str = "[]"

    # ── Ingestion scheduler ───────────────────────────────────────────────────
    INGESTION_ENABLED: bool = True          # master on/off switch
    INGESTION_RSS_INTERVAL_MIN: int = 10    # minutes between RSS polls
    INGESTION_TWITTER_INTERVAL_MIN: int = 5
    INGESTION_FACEBOOK_INTERVAL_MIN: int = 15
    INGESTION_TIKTOK_INTERVAL_MIN: int = 30

    # ── Telegram notifications ────────────────────────────────────────────────
    # Create a bot via @BotFather.  Get the chat/channel ID from @userinfobot
    # or by sending a message and calling getUpdates.
    TELEGRAM_BOT_TOKEN: str = ""
    # JSON array of chat IDs or @channel usernames, e.g.:
    # ["-100123456789", "@my_ops_channel"]
    TELEGRAM_CHAT_IDS: str = "[]"
    # Minimum severity level to trigger Telegram: low | medium | high | critical
    TELEGRAM_MIN_SEVERITY: str = "high"

    # ── Email (SMTP) notifications ────────────────────────────────────────────
    # Tested with Gmail (app password), Outlook, and generic SMTP relays.
    # For Gmail: enable 2-FA → generate App Password → use here.
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587                    # 587 = STARTTLS, 465 = SSL, 25 = plain
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""                     # defaults to SMTP_USERNAME if blank
    # JSON array of recipient email addresses:
    EMAIL_RECIPIENTS: str = "[]"
    # Minimum severity level to trigger email: low | medium | high | critical
    EMAIL_MIN_SEVERITY: str = "medium"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
