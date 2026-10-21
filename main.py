import os
import logging
import time
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

YUMCUT_API_KEY = (os.getenv("YUMCUT_API_KEY") or "").strip()
YUMCUT_API_BASE = "https://app.yumcut.com/api/user/v1"

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"

app = FastAPI(title="NEXUS-2070 // YumCut Ready", version="20.73.0")

# -----------------------------------------------------------------------------
# [2] FUNCIÓN PARA GENERAR VIDEO EN YUMCUT
# -----------------------------------------------------------------------------
def generar_video_yumcut(guion_texto: str):
    """Envía el guion a YumCut y espera a que el video esté listo."""
    if not YUMCUT_API_KEY:
        log.warning("[VIDEO] API Key de YumCut no configurada.")
        return None

    headers = {
        "Authorization": f"Bearer {YUMCUT_API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": f"nexus-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    }

    # Payload según la documentación de YumCut [citation:2][citation:16]
    payload = {
        "prompt": guion_texto,
        "projectExperience": "story",
        "durationSeconds": 30,  # Solicitamos 30 segundos
        "languages": ["es"],    # Español
        "captionsEnabled": True # Subtítulos activados
    }

    try:
        log.info("[VIDEO] Creando proyecto en YumCut...")
        resp = requests.post(f"{YUMCUT_API_BASE}/projects", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        project_data = resp.json()
        project_id = project_data.get("id")
        log.info(f"[VIDEO] Proyecto creado: {project_id}")

        # Polling: Consultamos el estado hasta que esté listo (máx 5 minutos)
        max_intentos = 30
        for i in range(max_intentos):
            time.sleep(10) # Espera 10 segundos entre consultas
            status_url = f"{YUMCUT_API_BASE}/projects/{project_id}/status"
            status_resp = requests.get(status_url, headers=headers, timeout=15)
            status_data = status_resp.json()
            status = status_data.get("status")
            
            log.info(f"[VIDEO] Estado ({i+1}/{max_intentos}): {status}")

            if status == "completed":
                # Obtener URL de descarga [citation:2]
                download_url = f"{YUMCUT_API_BASE}/projects/{project_id}/downloads/video"
                dl_resp = requests.get(download_url, headers=headers, timeout=15)
                dl_data = dl_resp.json()
                video_url = dl_data.get("url")
                log.info(f"[VIDEO] Video listo: {video_url}")
                return video_url
            elif status in ["failed", "stopped"]:
                log.error(f"[VIDEO] Proyecto falló o se detuvo: {status_data}")
                return None
        
        log.warning("[VIDEO] Timeout esperando a YumCut.")
        return None

    except Exception as e:
        log.error(f"[VIDEO] Error en YumCut: {e}")
        return None

# -----------------------------------------------------------------------------
# [3] ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"system": "NEXUS-2070", "status": "OPERATIONAL", "video_engine": "YumCut"}

@app.post("/generar-tendencias")
async def generar_tendencias():
    try:
        if not GROQ_API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return JSONResponse(status_code=502, content={"status": "ERROR", "detail": "Faltan credenciales base."})

        # 1. Generar guiones con Groq
        prompt = (
            "Genera 1 guion altamente viral para TikTok/Reels de 30 segundos. "
            "Estructura: GANCHO (3 segundos), CUERPO (5 líneas cortas), CTA. "
            "Prohibido promesas médicas o financieras falsas. Usa curiosidad y morbo."
        )
        headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload_groq = {
            "model": GROQ_MODEL,
            "messages": [{"role": "system", "content": "Eres un estratega viral."}, {"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 1024
        }

        log.info("[FLOW] Generando guion con Groq...")
        resp_groq = requests.post(GROQ_ENDPOINT, headers=headers_groq, json=payload_groq, timeout=45)
        resp_groq.raise_for_status()
        ai_text = resp_groq.json()["choices"][0]["message"]["content"]

        # 2. Enviar el guion de texto a Telegram (para que lo tengas de referencia)
        safe_text = ai_text.replace("*", "").replace("_", "").replace("`", "")
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"📝 *GUION GENERADO*\n\n{safe_text}",
            "parse_mode": "Markdown",
        }, timeout=15)

        # 3. Generar el video con YumCut
        log.info("[FLOW] Iniciando render de video en YumCut...")
        video_url = generar_video_yumcut(ai_text)

        if video_url:
            # 4. Enviar el video final a Telegram
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", json={
                "chat_id": TELEGRAM_CHAT_ID,
                "video": video_url,
                "caption": "🎬 *NEXUS-2070 // VIDEO LISTO* 🎬\n\nGenerado por YumCut con voz y subtítulos. ¡Listo para subir!",
                "parse_mode": "Markdown"
            }, timeout=30)
            return {"status": "SUCCESS", "video_url": video_url}
        else:
            return JSONResponse(status_code=502, content={"status": "VIDEO_ERROR", "detail": "YumCut no pudo generar el video."})

    except Exception as e:
        log.exception(f"[FLOW] Error crítico: {e}")
        return JSONResponse(status_code=502, content={"status": "INTERNAL_ERROR", "detail": str(e)})
