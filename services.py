import logging
import random
import json
import requests
import asyncio
from config import GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, TEMAS_POOL
from llm_router import llm_router

log = logging.getLogger("nexus.services")
COLA_TEMAS = []

def obtener_tema_aleatorio():
    global COLA_TEMAS
    if not COLA_TEMAS:
        COLA_TEMAS = TEMAS_POOL.copy()
        random.shuffle(COLA_TEMAS)
    seleccion = COLA_TEMAS.pop(0)
    return seleccion["tema"], seleccion["nicho"], seleccion["modo"]

def _disparar_github_sync(escenas, metadata):
    if not GITHUB_TOKEN or not GITHUB_OWNER or not GITHUB_REPO:
        log.error("❌ Faltan GITHUB_TOKEN, GITHUB_OWNER o GITHUB_REPO.")
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    payload = {"event_type": "render_video", "client_payload": {"scenes": escenas, "metadata": metadata}}
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 204:
            return True
        else:
            log.error(f"❌ GitHub rechazó la orden. Status: {r.status_code}. Respuesta: {r.text}")
            return False
    except Exception as e:
        log.error(f"❌ Error de red al conectar con GitHub: {e}")
        return False

async def procesar_video_async(tema: str, nicho: str, modo: str = "normal"):
    log.info(f"Iniciando generación con Multi-IA: {tema}")
    
    # Usamos el nuevo enrutador de IAs
    data = await llm_router.generar_guion_completo(tema, nicho)
    
    if not data or not data.get("escenas"): 
        log.warning("Se abortó el proceso porque no se pudo generar el guion.")
        return
    
    escenas = data.get("escenas", [])
    metadata = {
        "plataforma": data.get("plataforma", "YouTube"),
        "titulo": data.get("titulo", "Video"),
        "descripcion": data.get("descripcion", ""),
        "hashtags": data.get("hashtags", ""),
        "cta_link": data.get("cta_link", ""),
        "nicho_usado": f"{nicho} ({modo})"
    }
    
    exito = await asyncio.to_thread(_disparar_github_sync, escenas, metadata)
    if exito:
        log.info("✅ Orden enviada a GitHub Actions con éxito.")
    else:
        log.error("❌ Fallo al disparar GitHub Actions.")
