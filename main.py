# =============================================================================
# NEXUS-2070 // VIRAL CORE :: main.py
# -----------------------------------------------------------------------------
# Stack     : FastAPI + Groq (llama-3.3-70b-versatile) + Telegram Bot API
# Runtime   : Gunicorn + UvicornWorker (Render)
# Garantía  : Zero-Crash · Fail-Safe · Errores HTTP controlados
# =============================================================================

import os
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# -----------------------------------------------------------------------------
# [0] BOOTSTRAP
# -----------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | NEXUS-2070 | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("nexus")

# -----------------------------------------------------------------------------
# [1] CONFIG :: lectura segura con degradación controlada
# -----------------------------------------------------------------------------
GROQ_API_KEY: str = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN: str = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID: str = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

GROQ_ENDPOINT: str = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL: str = "llama-3.3-70b-versatile"
TELEGRAM_API: str = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" if TELEGRAM_TOKEN else ""

GROQ_TIMEOUT: int = 45
TELEGRAM_TIMEOUT: int = 15
MAX_TELEGRAM_LEN: int = 4096  # límite duro de Telegram


def _env_report() -> Dict[str, bool]:
    return {
        "groq": bool(GROQ_API_KEY),
        "telegram_token": bool(TELEGRAM_TOKEN),
        "telegram_chat": bool(TELEGRAM_CHAT_ID),
    }


ENV_STATUS = _env_report()

# -----------------------------------------------------------------------------
# [2] APP
# -----------------------------------------------------------------------------
app = FastAPI(
    title="NEXUS-2070 // Viral Core",
    description="Generador autónomo de guiones virales para Shorts/Reels/TikTok.",
    version="20.70.2",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -----------------------------------------------------------------------------
# [3] PROMPT MAESTRO
# -----------------------------------------------------------------------------
def _build_prompt() -> str:
    return (
        "Actúa como estratega senior de contenido viral. "
        "Genera EXACTAMENTE 3 guiones virales para Shorts/Reels/TikTok, "
        "cada uno de un nicho DIFERENTE (elige entre: cocina, tecnología, "
        "datos curiosos, misterio, finanzas, fitness, viajes, historia).\n\n"
        "ESTRUCTURA OBLIGATORIA por guion:\n"
        "• TITULO: nombre corto del guion (máx 8 palabras).\n"
        "• NICHO: categoría.\n"
        "• GANCHO: una sola frase de MÁXIMO 3 segundos al aire (potente, neuro-persuasiva).\n"
        "• CUERPO: exactamente 5 líneas ultra-cortas (máx 8 palabras cada una), "
        "pensadas para subtítulos dinámicos, una idea por línea.\n"
        "• CTA: una sola frase magnética de cierre.\n\n"
        "FORMATO DE SALIDA (crítico):\n"
        "- Usa el marcador literal '@@@' entre guiones.\n"
        "- Usa etiquetas en MAYÚSCULAS con dos puntos (TITULO:, NICHO:, GANCHO:, CUERPO:, CTA:).\n"
        "- NADA de markdown complejo, nada de tablas, nada de numeración extra.\n"
        "- Español neutro, tono directo, cero relleno."
    )


# -----------------------------------------------------------------------------
# [4] CLIENTE GROQ :: reintentos + parseo defensivo
# -----------------------------------------------------------------------------
class GroqError(Exception):
    """Error controlado del proveedor Groq."""


def _call_groq(retries: int = 2) -> str:
    if not GROQ_API_KEY:
        raise GroqError("GROQ_API_KEY no configurada en el entorno.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "Responde en español, tono directo, sin markdown complejo."},
            {"role": "user", "content": _build_prompt()},
        ],
        "temperature": 0.85,
        "top_p": 0.95,
        "max_tokens": 1600,
        "stream": False,
    }

    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                GROQ_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=GROQ_TIMEOUT,
            )
            if resp.status_code == 401:
                raise GroqError("Groq rechazó la API key (401).")
            if resp.status_code == 429:
                raise GroqError("Rate limit de Groq alcanzado (429).")
            resp.raise_for_status()

            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if not content or not content.strip():
                raise GroqError("Groq devolvió contenido vacío.")

            log.info(f"[GROQ] OK attempt={attempt} chars={len(content)}")
            return content.strip()

        except requests.exceptions.Timeout as e:
            last_err = GroqError(f"Timeout Groq ({GROQ_TIMEOUT}s).")
            log.warning(f"[GROQ] timeout attempt={attempt}")
        except requests.exceptions.RequestException as e:
            last_err = GroqError(f"Error de red Groq: {e}")
            log.warning(f"[GROQ] network attempt={attempt} :: {e}")
        except (KeyError, IndexError, ValueError) as e:
            raise GroqError(f"Respuesta Groq malformada: {e}")

        if attempt < retries:
            time.sleep(1.5 * attempt)

    raise last_err or GroqError("Fallo desconocido en Groq.")


# -----------------------------------------------------------------------------
# [5] FORMATEO TELEGRAM :: Markdown de alto impacto
# -----------------------------------------------------------------------------
def _sanitize_md(text: str) -> str:
    """Evita romper el parse_mode=Markdown (solo escapa lo crítico)."""
    return (
        text.replace("_", r"\_")
            .replace("*", r"\*")
            .replace("`", r"\`")
            .replace("[", r"\[")
    )


def _format_for_telegram(ai_text: str) -> str:
    guiones = [g.strip() for g in ai_text.split("@@@") if g.strip()]
    if not guiones:
        guiones = [ai_text.strip()]

    blocks = []
    for idx, g in enumerate(guiones[:3], start=1):
        safe = _sanitize_md(g)
        blocks.append(
            f"*🎬 GUION {idx}*\n"
            f"```\n{safe}\n```"
        )

    header = (
        "╔══════════════════════════════╗\n"
        "║ *NEXUS-2070 // VIRAL FEED* ║\n"
        "╚══════════════════════════════╝\n\n"
        f"🛰️ *Timestamp:* `{_utc_now()}`\n"
        f"🧠 *Motor:* `{GROQ_MODEL}`\n"
        "⚡ *Modo:* AUTÓNOMO\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    footer = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔻 _NEXUS-2070 · Zero-Human-in-the-Loop_"

    msg = header + "\n\n".join(blocks) + footer

    # Guardarraíl de longitud Telegram
    if len(msg) > MAX_TELEGRAM_LEN:
        msg = msg[: MAX_TELEGRAM_LEN - 20] + "\n…[truncado]"
    return msg


# -----------------------------------------------------------------------------
# [6] CLIENTE TELEGRAM
# -----------------------------------------------------------------------------
class TelegramError(Exception):
    """Error controlado del envío a Telegram."""


def _send_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise TelegramError("Credenciales de Telegram incompletas.")

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(TELEGRAM_API, json=payload, timeout=TELEGRAM_TIMEOUT)
    except requests.exceptions.Timeout:
        raise TelegramError(f"Timeout Telegram ({TELEGRAM_TIMEOUT}s).")
    except requests.exceptions.RequestException as e:
        raise TelegramError(f"Error de red Telegram: {e}")

    if resp.status_code >= 400:
        # Fallback: reintenta sin Markdown si el parseo falla
        log.warning(f"[TELEGRAM] HTTP {resp.status_code} :: reintento plain")
        try:
            resp2 = requests.post(
                TELEGRAM_API,
                json={**payload, "parse_mode": None, "text": message[: MAX_TELEGRAM_LEN - 1]},
                timeout=TELEGRAM_TIMEOUT,
            )
            if resp2.status_code < 400:
                log.info("[TELEGRAM] entregado en modo plain")
                return
        except requests.exceptions.RequestException:
            pass
        raise TelegramError(f"Telegram HTTP {resp.status_code}: {resp.text[:180]}")


# -----------------------------------------------------------------------------
# [7] ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/")
async def root() -> JSONResponse:
    online = all(ENV_STATUS.values())
    return JSONResponse(
        status_code=200,
        content={
            "system": "NEXUS-2070 // VIRAL CORE",
            "status": "OPERATIONAL" if online else "DEGRADED",
            "timestamp": _utc_now(),
            "modules": {
                "groq_llm": "ONLINE" if ENV_STATUS["groq"] else "MISSING_KEY",
                "telegram_token": "ONLINE" if ENV_STATUS["telegram_token"] else "MISSING",
                "telegram_chat": "ONLINE" if ENV_STATUS["telegram_chat"] else "MISSING",
            },
            "model": GROQ_MODEL,
        },
    )


@app.post("/generar-tendencias")
async def generar_tendencias() -> JSONResponse:
    """
    Orquestador:
      1) Groq → 3 guiones virales estructurados.
      2) Formatea para Telegram (Markdown).
      3) Despacha al chat configurado.
    Errores mapeados a códigos HTTP limpios (502/504/500).
    """
    try:
        log.info("[FLOW] iniciando generación...")
        ai_text = _call_groq()
        msg = _format_for_telegram(ai_text)
        _send_telegram(msg)

        return JSONResponse(
            status_code=200,
            content={
                "status": "SUCCESS",
                "timestamp": _utc_now(),
                "characters": len(ai_text),
                "preview": ai_text[:240] + ("..." if len(ai_text) > 240 else ""),
            },
        )

    except GroqError as e:
        log.error(f"[FLOW] GroqError :: {e}")
        code = 504 if "Timeout" in str(e) else 502
        return JSONResponse(
            status_code=code,
            content={"status": "AI_LAYER_ERROR", "detail": str(e), "timestamp": _utc_now()},
        )

    except TelegramError as e:
        log.error(f"[FLOW] TelegramError :: {e}")
        return JSONResponse(
            status_code=502,
            content={"status": "TELEGRAM_DELIVERY_ERROR", "detail": str(e), "timestamp": _utc_now()},
        )

    except Exception as e:
        log.exception(f"[FLOW] inesperado :: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "INTERNAL_ERROR", "detail": "Escudo NEXUS activado.", "timestamp": _utc_now()},
        )


# -----------------------------------------------------------------------------
# [8] STARTUP
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def _startup() -> None:
    log.info("=" * 58)
    log.info("NEXUS-2070 :: STARTUP")
    log.info(f"GROQ_KEY        :: {'SET' if ENV_STATUS['groq'] else 'MISSING'}")
    log.info(f"TELEGRAM_TOKEN  :: {'SET' if ENV_STATUS['telegram_token'] else 'MISSING'}")
    log.info(f"TELEGRAM_CHAT   :: {'SET' if ENV_STATUS['telegram_chat'] else 'MISSING'}")
    log.info("=" * 58)
