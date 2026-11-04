import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("nexus.micro_apps")
router = APIRouter(prefix="/api/v1/apps", tags=["Micro-Apps"])

class AppConfig(BaseModel):
    nombre_negocio: str
    nicho: str
    tono: str

# Base de datos simulada en memoria (reemplazar por Supabase en producción)
DB_APPS = {}

@router.get("/status")
async def get_status():
    """Endpoint para que el Dashboard vea el estado del sistema."""
    return {
        "status": "online",
        "apps_activas": len(DB_APPS),
        "version": "2.0.0 (Jarvis Core)"
    }

@router.post("/crear")
async def crear_micro_app(config: AppConfig):
    """Crea una nueva configuración para un cliente."""
    app_id = f"app_{config.nombre_negocio.lower().replace(' ', '_')}"
    DB_APPS[app_id] = config.model_dump()
    log.info(f"Micro-App creada: {app_id}")
    return {"status": "success", "app_id": app_id, "config": DB_APPS[app_id]}

@router.get("/{app_id}")
async def get_micro_app(app_id: str):
    """Obtiene la configuración de una app específica."""
    if app_id not in DB_APPS:
        raise HTTPException(status_code=404, detail="Micro-App no encontrada")
    return DB_APPS[app_id]
