import os
import json
import logging
import requests
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus")

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
GITHUB_OWNER = (os.getenv("GITHUB_OWNER") or "").strip()
GITHUB_REPO = (os.getenv("GITHUB_REPO") or "").strip()

CF_ACCOUNT_ID = "ead76709dc92c64a480ffca88bbc1b29"
CF_GATEWAY_ID = "i-a" 
CF_AUTH_TOKEN = (os.getenv("CF_AUTH_TOKEN") or "").strip()

app = FastAPI(title="Nexus V33.0 // Hybrid Brain")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "drama"

def generar_guion(tema: str, nicho: str):
    log.info(f"[GROQ] Generando guion para: {tema}")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.1"
    }
    
    prompt = f"""
    Actúa como un Guionista Senior experto en TikTok y YouTube Shorts.
    Genera un guion de 14 escenas sobre: '{tema}', con un tono de {nicho}.
    
    REGLAS DE ORO:
    1. GANCHO: La primera frase debe enganchar en 3 segundos.
    2. RITMO: Usa comas, NO puntos y seguido. Frases rápidas.
    3. LONGITUD: Exactamente entre 12 y 15 palabras por escena.
    
    REGLAS VISUALES (CRÍTICO):
    Para el campo "visual", escribe 1 o 2 palabras clave en INGLÉS (sustantivos o adjetivos). NO uses frases largas.
    Ejemplos válidos: "ancient pyramid", "dark forest", "glowing book", "space", "ocean", "mystery woman", "money", "sad man".
    Usa palabras que Pixabay pueda encontrar fácilmente.

    METADATOS:
    - Plataforma recomendada: "YouTube".
    - Un título adictivo de máximo 50 caracteres.
    - Una descripción persuasiva de 2 líneas.
    - 5 hashtags virales.
    - Un link o frase final para el CTA.

    DEBES responder ÚNICAMENTE con un JSON válido, sin markdown:
    {{
      "plataforma": "YouTube",
      "titulo": "Título adictivo",
      "descripcion": "Descripción persuasiva.",
      "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5",
      "cta_link": "Link o frase final",
      "escenas": [
        {{"texto": "Gancho neuro-persuasivo", "visual": "keyword1"}},
        {{"texto": "Secreto 1", "visual": "keyword2"}},
        {{"texto": "Secreto 2", "visual": "keyword3"}},
        {{"texto": "Dato oculto 1", "visual": "keyword4"}},
        {{"texto": "Dato oculto 2", "visual": "keyword5"}},
        {{"texto": "Giro inesperado", "visual": "keyword6"}},
        {{"texto": "Desarrollo 1", "visual": "keyword7"}},
        {{"texto": "Desarrollo 2", "visual": "keyword8"}},
        {{"texto": "Desarrollo 3", "visual": "keyword9"}},
        {{"texto": "Revelación 1", "visual": "keyword10"}},
        {{"texto": "Revelación 2", "visual": "keyword11"}},
        {{"texto": "Clímax", "visual": "keyword12"}},
        {{"texto": "Conclusión", "visual": "keyword13"}},
        {{"texto": "CTA final", "visual": "keyword14"}}
      ]
    }}
    """
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
        "response_format": {"type": "json_object"}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception as e:
        log.error(f"[GROQ] Error: {e}")
        return None

def disparar_github(escenas, metadata):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    payload = {"event_type": "render_video", "client_payload": {"scenes": escenas, "metadata": metadata}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r.status_code == 204
    except Exception:
        return False

def procesar_video_en_segundo_plano(tema: str, nicho: str):
    data = generar_guion(tema, nicho)
    if not data: return
    
    escenas = data.get("escenas", [])
    metadata = {
        "plataforma": data.get("plataforma", "YouTube"),
        "titulo": data.get("titulo", "Video"),
        "descripcion": data.get("descripcion", ""),
        "hashtags": data.get("hashtags", ""),
        "cta_link": data.get("cta_link", "")
    }

    if disparar_github(escenas, metadata):
        msg = f"🚀 *NEXUS HÍBRIDO* 🚀\n\nSe ha enviado el guion a GitHub Actions.\n\n📌 *Título:* {metadata['titulo']}\n🎯 *Plataforma:* {metadata['plataforma']}\n\n*El video llegará a este chat en unos minutos.*"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    else:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": "❌ Error al conectar con GitHub Actions."})

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V33.0"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, "El secreto de la Gran Pirámide", "drama")
    return {"status": "ACCEPTED"}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho)
    return {"status": "ACCEPTED"}
