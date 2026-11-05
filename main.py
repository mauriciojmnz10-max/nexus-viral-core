import logging
import time
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from services import procesar_video_async
from trends_researcher import obtener_temas_autonomos
import asyncio

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus.main")

app = FastAPI(title="Nexus V59.0 // Autonomía Secuencial")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "auto"
    modo: str = "normal"

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V59.0 (Secuencial)"}

def procesar_lote_temas(temas: list):
    """Procesa los temas uno por uno con pausas para evitar el error 429."""
    for i, t in enumerate(temas):
        log.info(f"Procesando tema {i+1}/{len(temas)}: {t['tema']}")
        # Aquí llamamos a la función de services de forma síncrona para el worker
        asyncio.run(procesar_video_async(t["tema"], t["nicho"], t["modo"]))
        
        # Si no es el último, esperamos 15 segundos antes del siguiente
        if i < len(temas) - 1:
            log.info("Esperando 15 segundos para no saturar Groq...")
            time.sleep(15)

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    temas = obtener_temas_autonomos(nicho_deseado="general")
    
    if not temas:
        return {"status": "ERROR", "detail": "No se pudieron obtener tendencias."}
    
    # Enviamos el lote completo a segundo plano para que se procese uno por uno
    background_tasks.add_task(procesar_lote_temas, temas)
    
    return {"status": "ACCEPTED", "temas_procesados": [t["tema"] for t in temas]}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_async, request.tema, request.nicho, request.modo)
    return {"status": "ACCEPTED"}
