import logging
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from services import procesar_video_async
from trends_researcher import obtener_temas_autonomos
import asyncio

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus.main")

app = FastAPI(title="Nexus V58.0 // Autonomía Total")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "auto"
    modo: str = "normal"

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V58.0 (Autónomo)"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    """
    Endpoint que usa el Cron-Job.
    Ahora va a buscar 3 tendencias reales de internet y las procesa.
    """
    # Buscamos temas autónomos. Por defecto, mezclaremos nichos o podríamos rotarlos.
    temas = obtener_temas_autonomos(nicho_deseado="general")
    
    if not temas:
        return {"status": "ERROR", "detail": "No se pudieron obtener tendencias."}
    
    # Procesamos los 3 temas en segundo plano
    for t in temas:
        background_tasks.add_task(procesar_video_async, t["tema"], t["nicho"], t["modo"])
    
    return {"status": "ACCEPTED", "temas_procesados": temas}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    """Endpoint para generar un tema específico (usado por la App Web)."""
    background_tasks.add_task(procesar_video_async, request.tema, request.nicho, request.modo)
    return {"status": "ACCEPTED"}
