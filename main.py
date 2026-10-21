# =============================================================================
# NEXUS-2070 :: CORE DE GENERACIÓN VIRAL AUTÓNOMA
# -----------------------------------------------------------------------------
# Arquitectura : FastAPI + Groq LLaMA 3.3 70B + Telegram Bot API
# Runtime      : Gunicorn + UvicornWorker (Render)
# Autor        : Ing. Principal de Sistemas Autónomos (2070)
# Garantía     : Zero-Crash · Fail-Safe · Telemetría Estructurada
# =============================================================================

import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# -----------------------------------------------------------------------------
# [0] BOOTSTRAP :: Carga de entorno y logging estructurado
# -----------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | NEXUS-2070 | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("nexus")

# -----------------------------------------------------------------------------
# [1] CONFIGURACIÓN :: Validación estricta con modo degradado (nunca crash)
# -----------------------------------------------------------------------------
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()

GROQ_ENDPOINT: str = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL: str = "llama-3.3-70b-versatile"
TELEGRAM_TIMEOUT: int = 15
GROQ_TIMEOUT: int = 45


def _validate_environment() -> Dict[str, bool]:
    """Diagnóstico no bloqueante: el sistema arranca siempre, reporta carencias."""
    status = {
        "groq": bool(GROQ_API_KEY),
        "telegram_token": bool(TELEGRAM_TOKEN),
        "telegram_chat": bool(TELEGRAM_CHAT_ID),
    }
    for k, ok in status.items():
        log.info(f"[ENV] {k:<16} :: {'ONLINE' if ok else 'MISSING'}")
    return status


ENV_STATUS = _validate_environment()

# -----------------------------------------------------------------------------
# [2] FASTAPI :: Instancia con metadatos ciber-futuristas
# -----------------------------------------------------------------------------
app = FastAPI(
    title="NEXUS-2070 // Viral Core",
    description="Sistema autónomo de generación predictiva de contenido viral.",
    version="20.70.0",
)


# -----------------------------------------------------------------------------
# [3] UTILIDADES INTERNAS
# -----------------------------------------------------------------------------
def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_groq_prompt() -> str:
    """Prompt maestro: neuro-persuasión + guiones optimizados para subtítulos."""
    return (
        "Eres un estratega de contenido viral del año 2070, especializado en "
        "neuro-persuasión y predicción algorítmica de tendencias. "
        "Analiza y predice las 3 tendencias globales MÁS EXPLOSIVAS de HOY "
        "en 3 nichos virales DIFERENTES entre sí (elige entre: cocina, "
        "tecnología, datos curiosos, misterio, finanzas, fitness, viajes). "
        "\n\nREGLAS ESTRICTAS DE FORMATO POR NICHO:\n"
        "1. Encabezado: nicho + emoji táctico.\n"
        "2. GANCHO NEURO-PERSUASIVO de 3 segundos (una sola línea, impacto máximo).\n"
        "3. DESARROLLO: exactamente 5 frases ULTRA-CORTAS (máx 8 palabras cada una), "
        "diseñadas para subtítulos automáticos tipo Shorts/Reels/TikTok.\n"
        "4. CTA MAGNÉTICO: una sola línea, alta conversión.\n"
        "5. HASHTAGS: 4 hashtags virales separados por espacio.\n"
        "\nSepara cada nicho con el marcador exacto: '---'.\n"
        "NO uses markdown complejo, NO uses tablas. Texto plano estructurado."
    )


def _sanitize_telegram(text: str) -> str:
    """Convierte marcadores de sección en separadores visuales futuristas."""
    return text.replace("---", "\n━━━━━━━━━━━━━━━━━━━━━━\n").strip()


def _call_groq() -> str:
    """Petición HTTP optimizada a Groq. Lanza excepción controlada si falla."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY ausente en el entorno.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Responde SIEMPRE en español, tono futurista, directo, sin relleno.",
            },
            {"role": "user", "content": _build_groq_prompt()},
        ],
        "temperature": 0.85,
        "max_tokens": 1400,
        "top_p": 0.95,
        "stream": False,
    }

    try:
        resp = requests.post(
            GROQ_ENDPOINT, headers=headers, json=payload, timeout=GROQ_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise RuntimeError("Groq devolvió contenido vacío.")
        return content.strip()
    except requests.exceptions.Timeout:
        raise RuntimeError("Timeout al contactar Groq (>45s).")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Fallo de red con Groq: {e}")
    except (KeyError, IndexError, ValueError) as e:
        raise RuntimeError(f"Respuesta Groq malformada: {e}")


def _send_telegram(message: str) -> bool:
    """Envío a Telegram. Devuelve True/False sin propagar excepción."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("[TELEGRAM] Credenciales incompletas :: skip")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT)
        if resp.status_code >= 400:
            log.error(f"[TELEGRAM] HTTP {resp.status_code} :: {resp.text[:200]}")
            return False
        return True
    except requests.exceptions.RequestException as e:
        log.error(f"[TELEGRAM] Excepción de red :: {e}")
        return False


def _format_telegram_payload(ai_content: str) -> str:
    """Envoltorio visual futurista de alto impacto."""
    body = _sanitize_telegram(ai_content)
    return (
        "╔══════════════════════════════╗\n"
        "║  *NEXUS-2070 // VIRAL FEED*  ║\n"
        "╚══════════════════════════════╝\n\n"
        f"🛰️ *Timestamp:* `{_utc_now()}`\n"
        f"🧠 *Motor:* `{GROQ_MODEL}`\n"
        f"⚡ *Modo:* PREDICTIVO-AUTÓNOMO\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{body}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔻 _Sistema NEXUS-2070 · Zero-Human-in-the-Loop_"
    )


# -----------------------------------------------------------------------------
# [4] ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/", tags=["core"])
async def root() -> JSONResponse:
    """Estado operativo del núcleo con estética ciber-futurista."""
    online = all(ENV_STATUS.values())
    return JSONResponse(
        status_code=200,
        content={
            "system": "NEXUS-2070 // VIRAL CORE",
            "status": "OPERATIONAL" if online else "DEGRADED",
            "timestamp": _utc_now(),
            "vector": "PRODUCTION",
            "modules": {
                "groq_llm": "ONLINE" if ENV_STATUS["groq"] else "MISSING_KEY",
                "telegram_token": "ONLINE" if ENV_STATUS["telegram_token"] else "MISSING",
                "telegram_chat": "ONLINE" if ENV_STATUS["telegram_chat"] else "MISSING",
            },
            "model": GROQ_MODEL,
            "uptime_signature": "🛰️ NEXUS_CORE::ALIVE",
        },
    )


@app.post("/generar-tendencias", tags=["core"])
async def generar_tendencias() -> JSONResponse:
    """
    Orquestador autónomo:
      1. Consulta predictiva a Groq (3 nichos virales del día).
      2. Estructura guiones neuro-persuasivos para Shorts/Reels/TikTok.
      3. Formatea payload futurista.
      4. Despacha a Telegram.
    Ante cualquier fallo: respuesta elegante (nunca silencio, nunca crash).
    """
    try:
        log.info("[FLOW] Iniciando generación de tendencias...")
        ai_content = _call_groq()
        log.info(f"[GROQ] OK :: {len(ai_content)} chars recibidos.")

        telegram_msg = _format_telegram_payload(ai_content)
        delivered = _send_telegram(telegram_msg)

        return JSONResponse(
            status_code=200,
            content={
                "status": "SUCCESS" if delivered else "PARTIAL",
                "timestamp": _utc_now(),
                "telegram_delivered": delivered,
                "content_preview": ai_content[:280] + ("..." if len(ai_content) > 280 else ""),
                "vector": "NEURO-PERSUASION::ACTIVE",
            },
        )

    except RuntimeError as e:
        log.error(f"[FLOW] Error controlado :: {e}")
        return JSONResponse(
            status_code=502,
            content={
                "status": "AI_LAYER_ERROR",
                "timestamp": _utc_now(),
                "detail": str(e),
                "hint": "Verifica GROQ_API_KEY y conectividad del proveedor.",
            },
        )
    except Exception as e:
        log.exception(f"[FLOW] Excepción inesperada :: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "INTERNAL_ERROR",
                "timestamp": _utc_now(),
                "detail": "Fallo capturado por el escudo NEXUS.",
            },
        )


# -----------------------------------------------------------------------------
# [5] LIFECYCLE HOOKS (telemetría de arranque)
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def _startup_event() -> None:
    log.info("=" * 60)
    log.info("NEXUS-2070 :: VIRAL CORE — ARRANQUE COMPLETO")
    log.info(f"Modelo LLM     :: {GROQ_MODEL}")
    log.info(f"Groq Key       :: {'SET' if ENV_STATUS['groq'] else 'MISSING'}")
    log.info(f"Telegram Token :: {'SET' if ENV_STATUS['telegram_token'] else 'MISSING'}")
    log.info(f"Telegram Chat  :: {'SET' if ENV_STATUS['telegram_chat'] else 'MISSING'}")
    log.info("=" * 60)
