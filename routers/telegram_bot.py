import logging
from fastapi import APIRouter, Request, BackgroundTasks
from config import settings
# Importamos la lógica de procesamiento (asegúrate de que services.py exista)
from services import procesar_video_async 

log = logging.getLogger("nexus.telegram")

router = APIRouter(prefix="/api/v1/telegram", tags=["Telegram Bot"])

async def procesar_mensaje_telegram_async(chat_id: str, texto: str):
    """
    Función que corre en segundo plano. 
    Aquí va la lógica que tarda tiempo (Groq, GitHub Actions, etc.)
    """
    log.info(f"[BG] Procesando mensaje asíncrono para chat {chat_id}: '{texto[:30]}...'")
    try:
        # Llamamos a tu lógica modular
        # Nota: Si tu services.py tiene otra función, ajústala aquí.
        await procesar_video_async(tema=texto, nicho="general", modo="normal")
    except Exception as e:
        log.error(f"Error en segundo plano: {e}")

@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recibe las actualizaciones de Telegram.
    Responde inmediatamente y delega el trabajo a BackgroundTasks.
    """
    try:
        data = await request.json()
        
        # Validación de seguridad (opcional, pero recomendada si configuras el webhook con secret)
        # secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        # if settings.TELEGRAM_WEBHOOK_SECRET and secret != settings.TELEGRAM_WEBHOOK_SECRET:
        #     return {"status": "unauthorized"}

        # Verificamos si es un mensaje de texto
        if "message" in data and "text" in data["message"]:
            chat_id = str(data["message"]["chat"]["id"])
            texto = data["message"]["text"]
            
            log.info(f"Mensaje recibido de {chat_id}. Enviando a BackgroundTasks...")
            
            # ¡La magia! Enviamos el trabajo a segundo plano y respondemos 200 OK al instante.
            background_tasks.add_task(procesar_mensaje_telegram_async, chat_id, texto)
            
            return {"status": "ok", "mensaje": "Procesando en segundo plano"}

        # Si es un callback query (botones) u otro tipo, puedes manejarlo aquí
        return {"status": "ignored"}
        
    except Exception as e:
        log.error(f"Error en el webhook de Telegram: {e}")
        # Devolvemos 200 OK incluso en error para que Telegram no reintente infinitamente
        return {"status": "error", "detalle": str(e)}
