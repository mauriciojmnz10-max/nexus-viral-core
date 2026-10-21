import os
import logging
from datetime import datetime, timezone
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus")

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
# ✅ Modelo de reemplazo oficial activo
GROQ_MODEL = "openai/gpt-oss-120b"

app = FastAPI(title="NEXUS-2070 // Viral Core", version="20.70.5")

@app.get("/")
async def root():
    return {"system": "NEXUS-2070", "status": "OPERATIONAL", "model": GROQ_MODEL}

@app.post("/generar-tendencias")
async def generar_tendencias():
    try:
        if not GROQ_API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return JSONResponse(status_code=502, content={"status": "ERROR", "detail": "Faltan credenciales en entorno."})

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "Eres un estratega de contenido viral. Responde en español directo."},
                {"role": "user", "content": "Genera 3 guiones cortos y virales para TikTok/Reels. Sepáralos con la marca '@@@'. No uses asteriscos ni guiones bajos."}
            ],
            "temperature": 0.8,
            "max_tokens": 1500
        }

        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=45)
        
        if response.status_code != 200:
            return JSONResponse(status_code=502, content={"status": "GROQ_ERROR", "detail": response.text})

        data = response.json()
        ai_text = data["choices"][0]["message"]["content"]

        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        safe_text = ai_text.replace("*", "").replace("_", "").replace("`", "")
        
        tg_payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚀 *NEXUS-2070 // REPORTE VIRAL* 🚀\n\n{safe_text}",
            "parse_mode": "Markdown",
        }
        tg_resp = requests.post(telegram_url, json=tg_payload, timeout=15)
        tg_resp.raise_for_status()

        return {"status": "SUCCESS", "model_used": GROQ_MODEL}

    except Exception as e:
        log.exception(f"Error crítico: {e}")
        return JSONResponse(status_code=502, content={"status": "INTERNAL_ERROR", "detail": str(e)})
