import os
import logging
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from groq import Groq
from dotenv import load_dotenv
import requests

# -----------------------------------------------------------------------------
# [0] BOOTSTRAP & LOGGING
# -----------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | NEXUS-2070 | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("nexus")

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

GROQ_MODEL = "llama-3.3-70b-versatile"

app = FastAPI(title="NEXUS-2070 // Viral Core", version="20.70.4")

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# -----------------------------------------------------------------------------
# [1] ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "system": "NEXUS-2070 // VIRAL CORE",
        "status": "OPERATIONAL" if GROQ_API_KEY else "DEGRADED",
        "timestamp": _utc_now(),
        "model": GROQ_MODEL,
    }

@app.post("/generar-tendencias")
async def generar_tendencias():
    try:
        log.info("[FLOW] Iniciando generación con cliente oficial de Groq...")
        
        if not GROQ_API_KEY:
            return JSONResponse(status_code=502, content={"status": "ERROR", "detail": "GROQ_API_KEY no configurada."})
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return JSONResponse(status_code=502, content={"status": "ERROR", "detail": "Credenciales de Telegram incompletas."})

        # 1. Llamada con el SDK oficial de Groq (con timeout explícito para evitar 502)
        client = Groq(api_key=GROQ_API_KEY, timeout=45.0)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un estratega de contenido viral. Responde en español, sin markdown complejo."},
                {"role": "user", "content": (
                    "Genera exactamente 3 guiones cortos y virales para TikTok/Reels/Shorts. "
                    "Incluye para cada uno: TÍTULO, GANCHO (3 segundos), CUERPO (líneas cortas para subtítulos) y CTA. "
                    "Sepáralos con la marca '@@@'. No uses asteriscos ni guiones bajos."
                )}
            ],
            model=GROQ_MODEL,
            temperature=0.8,
            max_tokens=1500,
        )
        
        ai_text = chat_completion.choices[0].message.content
        if not ai_text:
            raise ValueError("Groq devolvió contenido vacío.")

        # 2. Formateo seguro para Telegram (Evita errores de parseo Markdown)
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        
        # Sanitizamos el texto para que Telegram no falle si la IA pone un "*" o "_"
        safe_text = ai_text.replace("*", "").replace("_", "").replace("`", "")
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚀 *NEXUS-2070 // REPORTE VIRAL* 🚀\n\n{safe_text}",
            "parse_mode": "Markdown",
        }
        
        resp = requests.post(telegram_url, json=payload, timeout=15)
        resp.raise_for_status()
        
        log.info("[FLOW] ¡Tendencias generadas y enviadas con éxito!")
        return {"status": "SUCCESS", "timestamp": _utc_now()}

    except Exception as e:
        log.exception(f"[FLOW] Error crítico: {e}")
        return JSONResponse(
            status_code=502, 
            content={"status": "ERROR", "detail": str(e), "timestamp": _utc_now()}
        )
