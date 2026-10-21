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

MAGIC_HOUR_API_KEY = (os.getenv("MAGIC_HOUR_API_KEY") or "").strip()
MAGIC_HOUR_WEBHOOK_SECRET = (os.getenv("MAGIC_HOUR_WEBHOOK_SECRET") or "").strip()
WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or "").strip()

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"
MAGIC_HOUR_ENDPOINT = "https://api.magichour.ai/v1/text-to-video"

app = FastAPI(title="NEXUS-2070 // Video-Ready v3", version="20.72.0")

# -----------------------------------------------------------------------------
# [2] SOLICITAR VIDEO A MAGIC HOUR (uno por guion)
# -----------------------------------------------------------------------------
def solicitar_video_magic_hour(guion_texto: str, index: int):
    if not MAGIC_HOUR_API_KEY:
        log.warning("[VIDEO] API Key de Magic Hour no configurada.")
        return

    headers = {
        "Authorization": f"Bearer {MAGIC_HOUR_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Usamos un prompt visual limpio. Magic Hour no entiende de "Gancho/CTA",
    # solo de escenas visuales. Por eso le pasamos el texto descriptivo.
    payload = {
        "end_seconds": 5,
        "aspect_ratio": "9:16",
        "resolution": "480p",
        "model": "ltx-2.5",
        "style": {
            "prompt": f"Cinematic TikTok vertical video, scene: {guion_texto[:200]}"
        },
        "name": f"NEXUS_GUION_{index}_{datetime.now().strftime('%H%M%S')}",
        "webhook_url": WEBHOOK_URL
    }

    try:
        log.info(f"[VIDEO] Solicitando render para guion {index}...")
        resp = requests.post(MAGIC_HOUR_ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        log.info(f"[VIDEO] Render solicitado. ID: {data.get('id')}")
    except Exception as e:
        log.error(f"[VIDEO] Error al solicitar render {index}: {e}")

# -----------------------------------------------------------------------------
# [3] WEBHOOK (Recibe el aviso de Magic Hour)
# -----------------------------------------------------------------------------
@app.post("/webhook-video")
async def webhook_video(request: Request):
    try:
        # VALIDACIÓN DE SEGURIDAD (Magic Hour exige esto)
        signature = request.headers.get("X-MagicHour-Signature")
        if MAGIC_HOUR_WEBHOOK_SECRET and signature != MAGIC_HOUR_WEBHOOK_SECRET:
            log.warning("[WEBHOOK] Firma inválida. Ignorando.")
            return JSONResponse(status_code=401, content={"error": "invalid signature"})

        payload = await request.json()
        event_type = payload.get("type")
        data = payload.get("payload", {})
        
        log.info(f"[WEBHOOK] Evento: {event_type}")

        if event_type == "video.completed":
            # La URL está en downloads[0].url
            downloads = data.get("downloads", [])
            if downloads:
                video_url = downloads[0].get("url")
                job_id = data.get("id", "unknown")
                
                log.info(f"[WEBHOOK] Video listo: {job_id} -> {video_url}")
                
                telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
                tg_payload = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "video": video_url,
                    "caption": f"🎬 *NEXUS-2070 // VIDEO LISTO* 🎬\n\nID: `{job_id}`\n¡Listo para subir!",
                    "parse_mode": "Markdown"
                }
                requests.post(telegram_url, json=tg_payload, timeout=30)
                log.info("[WEBHOOK] Video enviado a Telegram.")
        
        elif event_type == "video.errored":
            log.error(f"[WEBHOOK] Error en render: {data.get('error')}")
            # Opcional: avisar a Telegram del error
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": f"⚠️ Error generando video: {data.get('error')}"},
                timeout=15
            )

        return {"status": "ok"}
    except Exception as e:
        log.error(f"[WEBHOOK] Error: {e}")
        return JSONResponse(status_code=500, content={"status": "error"})

# -----------------------------------------------------------------------------
# [4] ENDPOINTS PRINCIPALES
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"system": "NEXUS-2070", "status": "OPERATIONAL"}

@app.post("/generar-tendencias")
async def generar_tendencias():
    try:
        if not GROQ_API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return JSONResponse(status_code=502, content={"status": "ERROR", "detail": "Faltan credenciales."})

        prompt = (
            "Genera 3 guiones altamente virales para TikTok/Reels. "
            "Estructura: 1. GANCHO (3 seg), 2. CUERPO (5 líneas), 3. CTA. "
            "Separa con '》》》》》'. Prohibido promesas médicas o financieras falsas. "
            "Usa curiosidad y morbo."
        )

        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "system", "content": "Eres un estratega viral."}, {"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 2048
        }

        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=45)
        if response.status_code != 200:
            return JSONResponse(status_code=502, content={"status": "GROQ_ERROR", "detail": response.text})

        ai_text = response.json()["choices"][0]["message"]["content"]
        
        # Enviar texto a Telegram
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        safe_text = ai_text.replace("*", "").replace("_", "").replace("`", "")
        requests.post(telegram_url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚀 *NEXUS-2070 // GUIONES* 🚀\n\n{safe_text}",
            "parse_mode": "Markdown",
        }, timeout=15)

        # Disparar 3 videos (uno por guion)
        guiones = [g.strip() for g in ai_text.split("》》》》》") if g.strip()]
        for i, guion in enumerate(guiones[:3], start=1):
            solicitar_video_magic_hour(guion, i)

        return {"status": "SUCCESS", "videos_solicitados": min(len(guiones), 3)}

    except Exception as e:
        log.exception(f"[FLOW] Error crítico: {e}")
        return JSONResponse(status_code=502, content={"status": "INTERNAL_ERROR", "detail": str(e)})
