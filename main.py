import logging
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from config import TELEGRAM_TOKEN
from services import obtener_tema_aleatorio, procesar_video_async

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus.main")

app = FastAPI(title="Nexus V56.0 // Arquitectura Modular")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "auto"
    modo: str = "normal"

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V56.0 (Modular)"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    tema, nicho, modo = obtener_tema_aleatorio()
    # Procesamos en segundo plano con la función asíncrona segura
    background_tasks.add_task(procesar_video_async, tema, nicho, modo)
    return {"status": "ACCEPTED", "tema": tema}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_async, request.tema, request.nicho, request.modo)
    return {"status": "ACCEPTED"}
