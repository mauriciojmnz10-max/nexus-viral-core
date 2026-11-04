import logging
from fastapi import APIRouter, Request, BackgroundTasks
from config import settings
from llm_router import llm_router

log = logging.getLogger("nexus.telegram")
router = APIRouter(prefix="/api/v1/telegram", tags=["Telegram Bot"])

async def procesar_video_pesado(chat_id: str, texto: str):
    """Esta función corre en segundo plano (NO bloquea el servidor)."""
    log.info(f"[BG] Iniciando generación de video para chat {chat_id}...")
    
    # 1. El Enrutador de IAs investiga y redacta
    guion = await llm_router.route("redaccion", f"Genera un guion viral sobre: {texto}")
    
    # 2. Aquí iría la llamada a FFmpeg o GitHub Actions
    # (Simulamos una tarea pesada de 10 segundos)
    import asyncio
    await asyncio.sleep(10) 
    
    log.info(f"[BG] Video generado: {guion[:50]}...")
    # 3. Enviar a Telegram (usando httpx asíncrono)
    # ...

@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recibe actualizaciones de Telegram."""
    try:
        data = await request.json()
        
        # Validación de seguridad (Opcional pero recomendada)
        # if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != settings.TELEGRAM_WEBHOOK_SECRET:
        #     return {"status": "unauthorized"}

        if "message" in data and "text" in data["message"]:
            chat_id = str(data["message"]["chat"]["id"])
            texto = data["message"]["text"]
            
            # Enviamos el trabajo pesado a segundo plano y respondemos 200 OK inmediatamente
            background_tasks.add_task(procesar_video_pesado, chat_id, texto)
            
            return {"status": "ok", "mensaje": "Procesando en segundo plano"}

        return {"status": "ignored"}
    except Exception as e:
        log.error(f"Error en webhook de Telegram: {e}")
        return {"status": "error"}
