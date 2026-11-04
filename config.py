import os
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # --- Telegram ---
    TELEGRAM_TOKEN: str = Field(default="", env="TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID: str = Field(default="", env="TELEGRAM_CHAT_ID")
    TELEGRAM_WEBHOOK_SECRET: str = Field(default="", env="TELEGRAM_WEBHOOK_SECRET")

    # --- Supabase ---
    SUPABASE_URL: str = Field(default="", env="SUPABASE_URL")
    SUPABASE_KEY: str = Field(default="", env="SUPABASE_KEY")

    # --- IAs ---
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    DEEPSEEK_API_KEY: str = Field(default="", env="DEEPSEEK_API_KEY")
    CLAUDE_API_KEY: str = Field(default="", env="CLAUDE_API_KEY")
    GROQ_API_KEY: str = Field(default="", env="GROQ_API_KEY")

    # --- GitHub & Cloudflare ---
    GITHUB_TOKEN: str = Field(default="", env="GITHUB_TOKEN")
    GITHUB_OWNER: str = Field(default="", env="GITHUB_OWNER")
    GITHUB_REPO: str = Field(default="", env="GITHUB_REPO")
    CF_AUTH_TOKEN: str = Field(default="", env="CF_AUTH_TOKEN")
    
    # Valores por defecto para Cloudflare (o cárgalos de env si prefieres)
    CF_ACCOUNT_ID: str = os.getenv("CF_ACCOUNT_ID", "ead76709dc92c64a480ffca88bbc1b29")
    CF_GATEWAY_ID: str = os.getenv("CF_GATEWAY_ID", "i-a")

    class Config:
        env_file = ".env"
        extra = "ignore"

# Instancia global de la configuración
settings = Settings()

# ==============================================================================
# RETROCOMPATIBILIDAD: Alias globales
# ==============================================================================
# Esto permite que `from config import TELEGRAM_TOKEN` siga funcionando
# en los archivos que aún no hemos refactorizado. ¡Adiós al ImportError!
# ==============================================================================

TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN
TELEGRAM_CHAT_ID = settings.TELEGRAM_CHAT_ID
TELEGRAM_WEBHOOK_SECRET = settings.TELEGRAM_WEBHOOK_SECRET

SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY

GEMINI_API_KEY = settings.GEMINI_API_KEY
DEEPSEEK_API_KEY = settings.DEEPSEEK_API_KEY
CLAUDE_API_KEY = settings.CLAUDE_API_KEY
GROQ_API_KEY = settings.GROQ_API_KEY

GITHUB_TOKEN = settings.GITHUB_TOKEN
GITHUB_OWNER = settings.GITHUB_OWNER
GITHUB_REPO = settings.GITHUB_REPO
CF_AUTH_TOKEN = settings.CF_AUTH_TOKEN
CF_ACCOUNT_ID = settings.CF_ACCOUNT_ID
CF_GATEWAY_ID = settings.CF_GATEWAY_ID
