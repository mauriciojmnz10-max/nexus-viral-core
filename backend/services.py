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
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    if modo == "quiz":
        prompt = f"Genera un guion tipo QUIZ de 8 escenas sobre: '{tema}'. (Gancho, Pregunta 1, Respuesta 1, etc). REGLAS VISUALES: 2 palabras en INGLÉS."
    else:
        prompt = f"Actúa como Experto en {nicho} para YouTube Shorts. Genera un guion de 12 escenas sobre: '{tema}'. REGLAS VISUALES: 2 palabras en INGLÉS."

    prompt += "\nDevuelve SOLO un JSON: {\"plataforma\": \"YouTube\", \"titulo\": \"...\", \"descripcion\": \"...\", \"hashtags\": \"...\", \"cta_link\": \"...\", \"escenas\": [{\"texto\": \"...\", \"visual\": \"...\"}]}"
    
    payload = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "response_format": {"type": "json_object"}}
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = content.replace("```json", "").replace("```", "").strip()
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        return json.loads(content[start_idx:end_idx])
    except Exception as e:
        log.error(f"Error Groq: {e}")
        return None

def _disparar_github_sync(escenas, metadata):
    # Usamos repository_dispatch que es el que YA SABEMOS que funciona con tu render.yml
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    payload = {"event_type": "render_video", "client_payload": {"scenes": escenas, "metadata": metadata}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r.status_code == 204
    except: return False

async def procesar_video_async(tema: str, nicho: str, modo: str = "normal"):
    log.info(f"Iniciando generación: {tema}")
    
    data = await asyncio.to_thread(_generar_guion_sync, tema, nicho, modo)
    if not data: return
    
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
    if not exito:
        log.error("Fallo al disparar GitHub Actions.")
