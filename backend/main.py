import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from services import procesar_video_async

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus.main")

app = FastAPI(title="Nexus Studio API // Producción")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_origin_regex=r"https://.*\.vercel\.app", 
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"], 
)

class FrontendRequest(BaseModel):
    negocio: str
    nicho: str
    tono: Optional[str] = "Divertido"
    tema: str
    publico: Optional[str] = ""
    puntos_clave: Optional[str] = ""
    objetivo: Optional[str] = "Vender"

@app.get("/")
@app.get("/api/health")
async def health():
    return {"ok": True, "servicio": "nexus-studio", "motor": "github"}

@app.post("/api/generar")
async def generar_desde_web(request: FrontendRequest, background_tasks: BackgroundTasks):
    log.info(f"[WEB] Petición de: {request.negocio} | Tema: {request.tema}")
    
    # Construimos un tema mucho más rico para la IA
    tema_adaptado = f"{request.tema}. Público objetivo: {request.publico}. Puntos clave: {request.puntos_clave}. Objetivo: {request.objetivo}"
    
    background_tasks.add_task(procesar_video_async, tema_adaptado, request.nicho, "normal")
    
    return {
        "ok": True, 
        "mensaje": "Video en proceso. Te avisaremos por Telegram.",
        "job_id": "job_web_" + request.negocio.replace(" ", "_"),
        "video": {"titulo": request.tema}
    }
