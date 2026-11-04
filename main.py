import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings

# Importamos los routers modulares
from routers import telegram_bot
# from routers import micro_apps # Descomenta cuando tengas el router de micro-apps

# Configuración de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("nexus.main")

# Inicialización de la App
app = FastAPI(
    title="Nexus Viral Core",
    description="Arquitectura modular asíncrona para automatización de video.",
    version="2.0.0"
)

# CORS (Permite que Vercel y tu Dashboard se conecten)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Cambia esto por tu URL de Vercel en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montamos los routers
app.include_router(telegram_bot.router)

@app.get("/")
async def root():
    return {
        "sistema": "Nexus Viral Core",
        "status": "ONLINE",
        "arquitectura": "Modular / Async",
        "modulos": ["Telegram Webhook"]
    }

@app.get("/api/v1/health")
async def health():
    return {"ok": True, "servicio": "nexus-studio", "motor": "github"}
