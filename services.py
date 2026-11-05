import logging
import random
import json
import requests
import asyncio
from config import (
    GROQ_API_KEY, GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO,
    CF_ACCOUNT_ID, CF_GATEWAY_ID, CF_AUTH_TOKEN, TEMAS_POOL
)

log = logging.getLogger("nexus.services")
COLA_TEMAS = []

def obtener_tema_aleatorio():
    global COLA_TEMAS
    if not COLA_TEMAS:
        COLA_TEMAS = TEMAS_POOL.copy()
        random.shuffle(COLA_TEMAS)
    seleccion = COLA_TEMAS.pop(0)
    return seleccion["tema"], seleccion["nicho"], seleccion["modo"]

def _generar_guion_sync(tema: str, nicho: str, modo: str):
    if not GROQ_API_KEY or not CF_AUTH_TOKEN:
        log.error("❌ Faltan credenciales de Groq.")
        return None

    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    prompt = f"""
    Actúa como un Director de Cine y Guionista Viral Senior.
    Datos: {tema}
    
    REGLAS DEL TEXTO (CRÍTICO):
    - Menciona el nombre del negocio.
    - Tono: {nicho}.
    - Genera EXACTAMENTE 25 escenas para asegurar una duración de 60 segundos o más.
    - Escena 1: Gancho de 3 segundos ultra-adictivo.
    - Escenas 2 a 20: Desarrollo del tema (entre 15 y 20 palabras por escena).
    - Escenas 21 a 25: Llamado a la acción (CTA) MUY FUERTE. Pide explícitamente dar like, comentar, compartir y suscribirse/seguir para más contenido.

    REGLAS VISUALES (CRÍTICO):
    Para el campo "visual", escribe SOLO 1 PALABRA EN INGLÉS que represente el objeto físico principal de la escena.
    Ejemplo: "cheese", "scissors", "money", "gym", "doctor", "car", "phone".
    NO uses frases largas. Solo 1 palabra concreta.
    
    Devuelve SOLO un JSON válido con esta estructura exacta:
    {{
        "plataforma": "YouTube",
        "titulo": "Título adictivo",
        "descripcion": "Descripción persuasiva",
        "hashtags": "#tag1 #tag2 #tag3",
        "cta_link": "CTA",
        "escenas": [
            {{"texto": "Texto de la escena", "visual": "single_word"}}
        ]
    }}
    """
    
    payload = {
        "model": "openai/gpt-oss-120b", 
        "messages": [{"role": "user", "content": prompt}], 
        "temperature": 0.7, 
        "response_format": {"type": "json_object"}
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = content.replace("```json", "").replace("```", "").strip()
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        return json.loads(content[start_idx:end_idx])
    except Exception as e:
        log.error(f"❌ Error Groq: {e}")
        return None

def _disparar_github_sync(escenas, metadata):
    if not GITHUB_TOKEN or not GITHUB_OWNER or not GITHUB_REPO:
        log.error("❌ Faltan variables de GitHub.")
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    payload = {"event_type": "render_video", "client_payload": {"scenes": escenas, "metadata": metadata}}
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r.status_code == 204
    except: return False

async def procesar_video_async(tema: str, nicho: str, modo: str = "normal"):
    log.info(f"Iniciando generación: {tema[:50]}...")
    
    data = await asyncio.to_thread(_generar_guion_sync, tema, nicho, modo)
    if not data: 
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
    if exito: log.info("✅ Orden enviada a GitHub Actions.")
    else: log.error("❌ Fallo al disparar GitHub Actions.")
