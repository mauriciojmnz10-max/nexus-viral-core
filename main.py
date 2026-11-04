import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from services import obtener_tema_aleatorio, procesar_video_async

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus.main")

app = FastAPI(title="Nexus V58.0 // CORS Definitivo")

# 1. CONFIGURACIÓN DE CORS (DEBE IR ANTES DE CUALQUIER RUTA)
# Usamos allow_origin_regex para aceptar todos los dominios de Vercel (producción y previews)
# y allow_origins=["*"] como respaldo para otros orígenes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https://.*\.vercel\.app", # <--- ESTO ES LA CLAVE PARA VERCELL
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"], # Permitimos todas las cabeceras para evitar bloqueos
)

# --- MODELOS DE DATOS ---
class VideoRequest(BaseModel):
    tema: str
    nicho: str = "auto"
    modo: str = "normal"

class FrontendRequest(BaseModel):
    negocio: str
    nicho: str
    tono: Optional[str] = "Divertido"
    tema: str

# --- RUTAS ---

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V58.0"}

@app.get("/api/health")
async def health():
    return {"ok": True, "servicio": "nexus-studio", "motor": "github"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    tema, nicho, modo = obtener_tema_aleatorio()
    background_tasks.add_task(procesar_video_async, tema, nicho, modo)
    return {"status": "ACCEPTED", "tema": tema}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_async, request.tema, request.nicho, request.modo)
    return {"status": "ACCEPTED"}

# --- RUTA PUENTE PARA VERCELL ---

@app.post("/api/generar")
async def generar_desde_web(request: FrontendRequest, background_tasks: BackgroundTasks):
    log.info(f"[WEB] Petición recibida de: {request.negocio} | Tema: {request.tema}")
    tema_adaptado = f"{request.tema} (Enfocado para el negocio: {request.negocio})"
    background_tasks.add_task(procesar_video_async, tema_adaptado, request.nicho, "normal")
    return {
        "ok": True, 
        "mensaje": "Video en proceso. Te avisaremos por Telegram.",
        "job_id": "job_web_" + request.negocio.replace(" ", "_"),
        "video": {"titulo": request.tema}
    }
