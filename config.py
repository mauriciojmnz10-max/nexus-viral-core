import os
import logging
from pydantic_settings import BaseSettings
from pydantic import Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("nexus.config")

class Settings(BaseSettings):
    # Telegram
    TELEGRAM_TOKEN: str = Field(default="", env="TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID: str = Field(default="", env="TELEGRAM_CHAT_ID")
    TELEGRAM_WEBHOOK_SECRET: str = Field(default="", env="TELEGRAM_WEBHOOK_SECRET")

    # Supabase / DB
    SUPABASE_URL: str = Field(default="", env="SUPABASE_URL")
    SUPABASE_KEY: str = Field(default="", env="SUPABASE_KEY")

    # IAs (El enrutador)
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    DEEPSEEK_API_KEY: str = Field(default="", env="DEEPSEEK_API_KEY")
    CLAUDE_API_KEY: str = Field(default="", env="CLAUDE_API_KEY")

    # Entorno
    ENVIRONMENT: str = Field(default="production", env="ENVIRONMENT")
    PUBLIC_API_URL: str = Field(default="", env="PUBLIC_API_URL")

    class Config:
        env_file = ".env"
        extra = "ignore"

# Instancia global de configuración
settings = Settings()

# Validación de seguridad (Zero-Crash)
def validate_environment():
    missing = []
    if not settings.TELEGRAM_TOKEN: missing.append("TELEGRAM_TOKEN")
    if not settings.GEMINI_API_KEY and not settings.DEEPSEEK_API_KEY and not settings.CLAUDE_API_KEY: 
        missing.append("AL MENOS UNA API KEY DE IA")
    
    if missing:
        log.warning(f"⚠️ Variables de entorno faltantes: {', '.join(missing)}. El sistema arrancará en modo degradado.")
    else:
        log.info("✅ Todas las variables críticas están configuradas.")
