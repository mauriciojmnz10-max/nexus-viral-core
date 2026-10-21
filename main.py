import os
import logging
from datetime import datetime, timezone
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus")

# -----------------------------------------------------------------------------
# [1] VARIABLES DE ENTORNO
# -----------------------------------------------------------------------------
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

# Variables para Magic Hour
MAGIC_HOUR_API_KEY = (os.getenv("MAGIC_HOUR_API_KEY") or "").strip()
WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or "").strip()

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"

# Magic Hour Endpoint
MAGIC_HOUR_ENDPOINT = "https://api.magichour.ai/v1/text-to-video"

app = FastAPI(title="NEXUS-2070 // Video-Ready", version="20.71.0")

# -----------------------------------------------------------------------------
# [2] FUNCIÓN PARA SOLICITAR VIDEO A MAGIC HOUR
# -----------------------------------------------------------------------------
def solicitar_video_magic_hour(guion_texto: str):
    """Envía el guion a Magic Hour para generar el video."""
    if not MAGIC_HOUR_API_KEY:
        log.warning("[VIDEO] API Key de Magic Hour no configurada. Saltando video.")
        return

    headers = {
        "Authorization": f"Bearer {MAGIC_HOUR_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Payload según la documentación de Magic Hour
    # Usamos wan-2.2 que es el modelo por defecto gratuito (24 créditos/seg) [citation:8]
    payload = {
        "end_seconds": 5,           # 5 segundos (gasta ~120 créditos)
        "aspect_ratio": "9:16",     # Vertical para TikTok/Reels
        "resolution": "480p",       # Resolución gratuita [citation:7]
        "model": "wan-2.2",         # Modelo gratuito por defecto [citation:8]
        "style": {
            "prompt": guion_texto   # El prompt visual
        },
        "name": f"NEXUS_{datetime.now().strftime('%H%M%S')}",
        "webhook_url": WEBHOOK_URL  # Para que nos avise cuando termine
    }

    try:
        log.info("[VIDEO] Solicitando render a Magic Hour...")
        resp = requests.post(MAGIC_HOUR_ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        log.info(f"[VIDEO] Render solicitado. ID: {data.get('id')}")
    except Exception as e:
        log.error(f"[VIDEO] Error al solicitar render: {e}")

# -----------------------------------------------------------------------------
# [3] ENDPOINT DE WEBHOOK (Recibe el aviso de Magic Hour)
# -----------------------------------------------------------------------------
@app.post("/webhook-video")
async def webhook_video(request: Request):
    """Recibe la notificación de Magic Hour cuando el video está listo."""
    try:
        payload = await request.json()
        log.info(f"[VIDEO-WEBHOOK] Notificación recibida: {payload}")
        
        # Magic Hour envía el estado y la URL en 'downloads'
        if payload.get("status") == "completed":
            downloads = payload.get("downloads", [])
            if downloads and len(downloads) > 0:
                video_url = downloads[0].get("url")
                
                if video_url:
                    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
                    tg_payload = {
                        "chat_id": TELEGRAM_CHAT_ID,
                        "video": video_url,
                        "caption": "🎬 *NEXUS-2070 // VIDEO LISTO* 🎬\n\nGenerado por Magic Hour. ¡Listo para subir!",
                        "parse_mode": "Markdown"
                    }
                    requests.post(telegram_url, json=tg_payload, timeout=30)
                    log.info("[VIDEO-WEBHOOK] Video enviado a Telegram.")
            
        return {"status": "received"}
    except Exception as e:
        log.error(f"[VIDEO-WEBHOOK] Error: {e}")
        return JSONResponse(status_code=500, content={"status": "error"})

# -----------------------------------------------------------------------------
# [4] ENDPOINTS PRINCIPALES
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"system": "NEXUS-2070", "status": "OPERATIONAL", "model": GROQ_MODEL}

@app.post("/generar-tendencias")
async def generar_tendencias():
    try:
        if not GROQ_API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return JSONResponse(status_code=502, content={"status": "ERROR", "detail": "Faltan credenciales."})

        # Prompt blindado (Anti-Shadowban)
        prompt = (
            "Genera 3 guiones altamente virales para TikTok/Reels usando psicología de retención "
            "(Curiosity Gap, FOMO y Storytelling), pero SIN violar las normas de la comunidad.\n\n"
            "REGLAS DE ORO:\n"
            "- PROHIBIDO prometer resultados médicos reales o curas milagrosas.\n"
            "- PROHIBIDO prometer riquezas garantizadas o dinero fácil.\n"
            "- Usa el morbo, los secretos de la industria, o datos históricos sorprendentes.\n\n"
            "ESTRUCTURA POR GUION:\n"
            "1. GANCHO (Frase exacta de 3 segundos, máxima curiosidad).\n"
            "2. CUERPO (5 líneas cortas para subtítulos dinámicos).\n"
            "3. CTA (Llamado a la acción magnético).\n\n"
            "Separa cada guion EXACTAMENTE con la marca '》》》》》'. No uses asteriscos ni guiones bajos."
        )

        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "system", "content": "Eres un estratega viral."}, {"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 2048
        }

        log.info("[FLOW] Enviando petición a Groq...")
        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=45)
        
        if response.status_code != 200:
            return JSONResponse(status_code=502, content={"status": "GROQ_ERROR", "detail": response.text})

        data = response.json()
        ai_text = data["choices"][0]["message"]["content"]
        if not ai_text:
            raise ValueError("Groq devolvió vacío.")

        # Enviar texto a Telegram
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        safe_text = ai_text.replace("*", "").replace("_", "").replace("`", "")
        tg_payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚀 *NEXUS-2070 // REPORTE VIRAL* 🚀\n\n{safe_text}",
            "parse_mode": "Markdown",
        }
        requests.post(telegram_url, json=tg_payload, timeout=15)

        # NUEVO: Disparar video con el PRIMER guion
        # Extraemos el primer guion (antes del separador)
        primer_guion = ai_text.split("》》》》》")[0]
        solicitar_video_magic_hour(primer_guion)

        return {"status": "SUCCESS", "model_used": GROQ_MODEL, "video_requested": True}

    except Exception as e:
        log.exception(f"[FLOW] Error crítico: {e}")
        return JSONResponse(status_code=502, content={"status": "INTERNAL_ERROR", "detail": str(e)})
