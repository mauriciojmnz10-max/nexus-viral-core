import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
GITHUB_OWNER = (os.getenv("GITHUB_OWNER") or "").strip()
GITHUB_REPO = (os.getenv("GITHUB_REPO") or "").strip()

CF_ACCOUNT_ID = "ead76709dc92c64a480ffca88bbc1b29"
CF_GATEWAY_ID = "i-a" 
CF_AUTH_TOKEN = (os.getenv("CF_AUTH_TOKEN") or "").strip()

# --- POOL DE TEMAS (Para el bot de Telegram) ---
TEMAS_POOL = [
    {"tema": "El error de las tarjetas de crédito", "nicho": "finanzas", "modo": "normal"},
    {"tema": "Cómo ahorrar sin darte cuenta", "nicho": "finanzas", "modo": "normal"},
    {"tema": "La trampa de los préstamos rápidos", "nicho": "finanzas", "modo": "normal"},
    {"tema": "La IA que te quitará el trabajo", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "Cómo proteger tu privacidad en internet", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "Tus derechos si te detiene la policía", "nicho": "legal", "modo": "normal"},
    {"tema": "El hábito que destruye tu sueño", "nicho": "salud", "modo": "normal"},
    {"tema": "Cómo manipulan tu mente los anuncios", "nicho": "psicologia", "modo": "normal"},
    {"tema": "La regla de los 5 segundos para vencer la pereza", "nicho": "motivacion", "modo": "normal"},
    {"tema": "El secreto oculto de la Gran Muralla China", "nicho": "historia", "modo": "normal"},
    {"tema": "El código oculto en la Mona Lisa", "nicho": "misterio", "modo": "normal"},
    {"tema": "Quiz: ¿Cuánto sabes de historia universal?", "nicho": "cultura general", "modo": "quiz"},
    {"tema": "Quiz: Adivina el país por su bandera", "nicho": "geografia", "modo": "quiz"}
]
