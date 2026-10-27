"""
Nexus Studio · API Gateway (FastAPI)
====================================
Puente entre el dashboard web (React) y tu motor de generación de videos
(Groq + Pixabay + FFmpeg + Telegram).

Ejecutar en local:
    pip install -r requirements.txt
    cp .env.example .env
    uvicorn main:app --reload --port 8000

Endpoints:
    GET  /api/health             -> estado del servicio
    POST /api/generar            -> valida datos y dispara el motor
    GET  /api/videos             -> últimos videos generados
    GET  /api/videos/{id}        -> estado de un video
    POST /api/videos/callback    -> el motor avisa que terminó (protegido con secreto)
"""

import logging
import os
import secrets
import threading
import time
import unicodedata
import re
import uuid
from collections import OrderedDict, defaultdict, deque
from datetime import datetime, timezone
from typing import Literal, Optional

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

try:  # .env es opcional: en producción usa variables de entorno reales
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("nexus.api")


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
class Settings:
    """Lee toda la configuración desde variables de entorno."""

    def __init__(self) -> None:
        # Motor: "mock" (simulado) | "github" (GitHub Actions) | "webhook" (Render u otro)
        self.engine_mode = os.getenv("ENGINE_MODE", "mock").strip().lower()
        self.engine_timeout = float(os.getenv("ENGINE_TIMEOUT", "15"))

        # CORS: lista separada por comas con los orígenes del frontend
        self.allowed_origins = [
            o.strip()
            for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]

        # Seguridad
        self.api_key = os.getenv("NEXUS_API_KEY", "")  # vacío = sin API key
        self.callback_secret = os.getenv("CALLBACK_SECRET", "")
        self.rate_limit_per_min = int(os.getenv("RATE_LIMIT_PER_MIN", "5"))

        # GitHub Actions
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.github_repo = os.getenv("GITHUB_REPO", "")  # "usuario/repositorio"
        self.github_workflow = os.getenv("GITHUB_WORKFLOW", "generar_video.yml")
        self.github_ref = os.getenv("GITHUB_REF_NAME", "main")

        # Webhook genérico (Render, n8n, tu propio servidor...)
        self.webhook_url = os.getenv("ENGINE_WEBHOOK_URL", "")
        self.webhook_token = os.getenv("ENGINE_WEBHOOK_TOKEN", "")

        # URL pública de esta API (para que el motor pueda llamar al callback)
        self.public_api_url = os.getenv("PUBLIC_API_URL", "").rstrip("/")

        # Solo modo mock
        self.mock_delay_seconds = float(os.getenv("MOCK_DELAY_SECONDS", "9"))
        self.telegram_channel_url = os.getenv("TELEGRAM_CHANNEL_URL", "https://t.me/")


settings = Settings()


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class GenerarRequest(BaseModel):
    negocio: str = Field(..., min_length=2, max_length=80)
    nicho: str = Field(..., min_length=2, max_length=40)
    tono: str = Field(default="Divertido", min_length=2, max_length=30)
    tema: str = Field(..., min_length=3, max_length=300)

    @field_validator("negocio", "nicho", "tono", "tema", mode="before")
    @classmethod
    def limpiar_espacios(cls, value):
        return value.strip() if isinstance(value, str) else value


class CallbackRequest(BaseModel):
    job_id: str
    estado: Literal["listo", "error"] = "listo"
    titulo: Optional[str] = Field(default=None, max_length=200)
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    telegram_url: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_hashtag(texto: str) -> str:
    """'Corte de pelo' -> 'CorteDePelo' (sin tildes ni símbolos)."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    palabras = re.findall(r"[A-Za-z0-9]+", sin_tildes)
    return "".join(p.capitalize() for p in palabras)


def construir_hashtags(datos: GenerarRequest) -> list[str]:
    candidatos = [datos.nicho, datos.negocio, "viral", "fyp", "shorts"]
    candidatos += [t for t in re.split(r"[,\n;]", datos.tema) if t.strip()][:3]
    vistos: list[str] = []
    for c in candidatos:
        tag = slug_hashtag(c)
        if tag and len(tag) <= 30 and f"#{tag}" not in vistos:
            vistos.append(f"#{tag}")
    return vistos[:6]


class VideoStore:
    """Historial en memoria, seguro entre hilos.

    En producción reemplázalo por Postgres/Supabase/Redis: la memoria se
    pierde al reiniciar el servidor y no se comparte entre workers.
    """

    def __init__(self, max_items: int = 50) -> None:
        self._items: "OrderedDict[str, dict]" = OrderedDict()
        self._lock = threading.Lock()
        self._max = max_items

    def create(self, record: dict) -> dict:
        with self._lock:
            self._items[record["id"]] = record
            while len(self._items) > self._max:
                self._items.popitem(last=False)
            return dict(record)

    def update(self, job_id: str, **changes) -> Optional[dict]:
        with self._lock:
            record = self._items.get(job_id)
            if record is None:
                return None
            record.update(changes)
            return dict(record)

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            record = self._items.get(job_id)
            return dict(record) if record else None

    def latest(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return [dict(r) for r in list(self._items.values())[::-1][:limit]]


class RateLimiter:
    """Límite simple por cliente (ventana deslizante de 60 s, en memoria)."""

    def __init__(self, max_calls: int, window: int = 60) -> None:
        self._max = max_calls
        self._window = window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self._max <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self._window:
                hits.popleft()
            if len(hits) >= self._max:
                return False
            hits.append(now)
            return True


store = VideoStore()
limiter = RateLimiter(settings.rate_limit_per_min)


# ---------------------------------------------------------------------------
# Motor de generación
# ---------------------------------------------------------------------------
class EngineError(Exception):
    """El motor no aceptó o no pudo recibir la orden."""


def _finalizar_mock(job_id: str, datos: dict) -> None:
    """Simula que el motor terminó el video (solo ENGINE_MODE=mock)."""
    tema = datos["tema"].split(",")[0].strip().capitalize()
    store.update(
        job_id,
        estado="listo",
        titulo=f"{tema}: lo que nadie te cuenta",
        telegram_url=settings.telegram_channel_url,
        download_url=None,
    )
    log.info("[mock] job %s marcado como listo", job_id)


def disparar_motor(job_id: str, datos: GenerarRequest) -> str:
    """Envía la orden al motor existente. Devuelve el modo usado."""
    mode = settings.engine_mode
    inputs = {
        "job_id": job_id,
        "negocio": datos.negocio,
        "nicho": datos.nicho,
        "tono": datos.tono,
        "tema": datos.tema,
        "callback_url": (
            f"{settings.public_api_url}/api/videos/callback" if settings.public_api_url else ""
        ),
    }

    if mode == "mock":
        timer = threading.Timer(
            settings.mock_delay_seconds, _finalizar_mock, args=(job_id, datos.model_dump())
        )
        timer.daemon = True
        timer.start()
        return "mock"

    try:
        if mode == "github":
            if not (settings.github_token and settings.github_repo):
                raise EngineError("Falta GITHUB_TOKEN o GITHUB_REPO en la configuración.")
            resp = requests.post(
                f"https://api.github.com/repos/{settings.github_repo}"
                f"/actions/workflows/{settings.github_workflow}/dispatches",
                headers={
                    "Authorization": f"Bearer {settings.github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"ref": settings.github_ref, "inputs": inputs},
                timeout=settings.engine_timeout,
            )
            if resp.status_code != 204:  # GitHub responde 204 sin cuerpo si todo va bien
                raise EngineError(f"GitHub rechazó la orden ({resp.status_code}).")
            return "github"

        if mode == "webhook":
            if not settings.webhook_url:
                raise EngineError("Falta ENGINE_WEBHOOK_URL en la configuración.")
            headers = {"Content-Type": "application/json"}
            if settings.webhook_token:
                headers["Authorization"] = f"Bearer {settings.webhook_token}"
            resp = requests.post(
                settings.webhook_url, json=inputs, headers=headers, timeout=settings.engine_timeout
            )
            if not resp.ok:
                raise EngineError(f"El motor respondió {resp.status_code}.")
            return "webhook"

        raise EngineError(f"ENGINE_MODE desconocido: '{mode}'.")

    except requests.RequestException as exc:
        raise EngineError(f"No se pudo contactar al motor: {exc.__class__.__name__}") from exc


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Nexus Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if settings.api_key and not secrets.compare_digest(x_api_key or "", settings.api_key):
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")


@app.exception_handler(RequestValidationError)
async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Datos faltantes o inválidos -> 400 (en vez del 422 por defecto)."""
    detalles = [
        {"campo": str(e["loc"][-1]), "mensaje": e["msg"]} for e in exc.errors() if e.get("loc")
    ]
    campos = sorted({d["campo"] for d in detalles})
    return JSONResponse(
        status_code=400,
        content={
            "ok": False,
            "error": "Faltan datos o son inválidos: " + ", ".join(campos),
            "campos": campos,
            "detalles": detalles,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})


@app.exception_handler(Exception)
async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
    log.exception("Error no controlado: %s", exc)
    return JSONResponse(
        status_code=500, content={"ok": False, "error": "Error interno del servidor."}
    )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "servicio": "nexus-studio", "motor": settings.engine_mode}


@app.post("/api/generar", dependencies=[Depends(require_api_key)])
def generar(datos: GenerarRequest, request: Request) -> dict:
    cliente = request.client.host if request.client else "desconocido"
    if not limiter.allow(cliente):
        raise HTTPException(
            status_code=429, detail="Demasiadas solicitudes. Espera un minuto e inténtalo de nuevo."
        )

    job_id = uuid.uuid4().hex[:12]
    record = store.create(
        {
            "id": job_id,
            "negocio": datos.negocio,
            "nicho": datos.nicho,
            "tono": datos.tono,
            "tema": datos.tema,
            "titulo": datos.tema,
            "hashtags": construir_hashtags(datos),
            "estado": "procesando",
            "creado": ahora_iso(),
            "telegram_url": None,
            "download_url": None,
            "error": None,
        }
    )

    try:
        modo = disparar_motor(job_id, datos)
    except EngineError as exc:
        log.error("Fallo al disparar el motor (job %s): %s", job_id, exc)
        store.update(job_id, estado="error", error=str(exc))
        raise HTTPException(
            status_code=502, detail="El motor de video no está disponible. Inténtalo más tarde."
        ) from exc

    log.info("Job %s enviado al motor (%s) para '%s'", job_id, modo, datos.negocio)
    return {
        "ok": True,
        "mensaje": "Video en proceso. Te avisaremos cuando esté listo.",
        "job_id": job_id,
        "modo_motor": modo,
        "video": record,
    }


@app.get("/api/videos", dependencies=[Depends(require_api_key)])
def listar_videos(limit: int = 20) -> dict:
    limit = max(1, min(limit, 50))
    return {"ok": True, "videos": store.latest(limit)}


@app.get("/api/videos/{job_id}", dependencies=[Depends(require_api_key)])
def obtener_video(job_id: str) -> dict:
    record = store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Video no encontrado.")
    return {"ok": True, "video": record}


@app.post("/api/videos/callback")
def callback_motor(
    datos: CallbackRequest, x_callback_secret: Optional[str] = Header(default=None)
) -> dict:
    """El motor llama aquí al terminar para publicar título, hashtags y enlaces."""
    if not settings.callback_secret:
        raise HTTPException(status_code=503, detail="Callback no configurado (CALLBACK_SECRET).")
    if not secrets.compare_digest(x_callback_secret or "", settings.callback_secret):
        raise HTTPException(status_code=401, detail="Secreto de callback inválido.")

    cambios: dict = {"estado": datos.estado, "error": datos.error}
    if datos.titulo:
        cambios["titulo"] = datos.titulo
    if datos.hashtags:
        cambios["hashtags"] = datos.hashtags
    if datos.telegram_url:
        cambios["telegram_url"] = datos.telegram_url
    if datos.download_url:
        cambios["download_url"] = datos.download_url

    if store.update(datos.job_id, **cambios) is None:
        raise HTTPException(status_code=404, detail="Video no encontrado.")
    log.info("Callback recibido: job %s -> %s", datos.job_id, datos.estado)
    return {"ok": True}
