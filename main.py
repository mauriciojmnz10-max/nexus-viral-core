import os
import logging
from datetime import datetime, timezone
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus")

# -----------------------------------------------------------------------------
# [1] VARIABLES DE ENTORNO
# -----------------------------------------------------------------------------
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"

app = FastAPI(title="NEXUS-2070 // Viral Core", version="20.70.6")

# -----------------------------------------------------------------------------
# [2] ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"system": "NEXUS-2070", "status": "OPERATIONAL", "model": GROQ_MODEL}

@app.post("/generar-tendencias")
async def generar_tendencias():
    try:
        if not GROQ_API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return JSONResponse(
                status_code=502, 
                content={"status": "ERROR", "detail": "Faltan credenciales en el entorno."}
            )

        # Prompt optimizado y corregido (sin errores de sintaxis)
        prompt = (
            "Genera 3 guiones hipersensacionalistas para TikTok/Reels. "
            "Estructura estricta para cada uno:\n"
            "1. GANCHO (Frase exacta para decir en los primeros 3 segundos, máxima curiosidad).\n"
            "2. CUERPO (Máximo 5 líneas cortas, directas, para leer en pantalla o decir rápido).\n"
            "3. CTA (Llamado a la acción magnético).\n"
            "Separa cada guion con la marca '》》》》》'. No uses asteriscos ni guiones bajos."
        )

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system", 
                    "content": "Eres un estratega de contenido viral. Responde en español directo y sin rodeos."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.8,
            "max_tokens": 2048  # Aumentado para evitar respuestas vacías del modelo 120b
        }

        log.info("[FLOW] Enviando petición a Groq...")
        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=45)
        
        if response.status_code != 200:
            log.error(f"[GROQ] Error {response.status_code}: {response.text}")
            return JSONResponse(
                status_code=502, 
                content={"status": "GROQ_ERROR", "detail": response.text}
            )

        data = response.json()
        ai_text = data["choices"][0]["message"]["content"]
        
        if not ai_text:
            raise ValueError("Groq devolvió una respuesta vacía.")

        # Limpieza de Markdown para evitar que Telegram rechace el mensaje
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        safe_text = ai_text.replace("*", "").replace("_", "").replace("`", "")
        
        tg_payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚀 *NEXUS-2070 // REPORTE VIRAL* 🚀\n\n{safe_text}",
            "parse_mode": "Markdown",
        }
        
        log.info("[FLOW] Enviando reporte a Telegram...")
        tg_resp = requests.post(telegram_url, json=tg_payload, timeout=15)
        tg_resp.raise_for_status()

        log.info("[FLOW] ¡Éxito total!")
        return {"status": "SUCCESS", "model_used": GROQ_MODEL, "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

    except requests.exceptions.Timeout:
        log.error("[FLOW] Timeout: La petición tardó demasiado.")
        return JSONResponse(status_code=504, content={"status": "TIMEOUT", "detail": "El servidor tardó demasiado en responder."})
    
    except Exception as e:
        log.exception(f"[FLOW] Error crítico: {e}")
        return JSONResponse(status_code=502, content={"status": "INTERNAL_ERROR", "detail": str(e)})
