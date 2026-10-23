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

app = FastAPI(title="Nexus V44.0 // Real Data Brain")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "datos curiosos"

def generar_guion(tema: str, nicho: str):
    log.info(f"[GROQ] Generando guion de datos reales para: {tema}")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    prompt = f"""
    Actúa como un Investigador y Guionista Senior experto en YouTube Shorts (estilo documental de misterio y ciencia).
    Genera un guion de 12 escenas sobre: '{tema}'.
    
    REGLAS DE ORO (CRÍTICO):
    1. PROHIBIDO INVENTAR: Usa datos reales, matemáticas, proporciones, historia o ciencia. NADA de magia, fantasmas o trampas mortales.
    2. GANCHO: Empieza con una pregunta matemática o un dato de impacto real. (Ej: "¿Sabías que si divides el perímetro de la pirámide entre su altura...?").
    3. TONO: Analítico, de revelación intelectual. No es una película de terror, es un documental sorprendente.
    4. RITMO: Frases rápidas, usa comas. Máximo 12 palabras por escena.
    
    REGLAS VISUALES (COHERENCIA ESTRICTA):
    Para el campo "visual", escribe EXACTAMENTE 2 palabras clave en INGLÉS que representen objetos o lugares FÍSICOS y REALES de lo que habla el texto.
    NO uses conceptos abstractos. 
    Ejemplo: Si habla de la pirámide, escribe "pyramid egypt". Si habla de matemáticas, escribe "math compass". Si habla de satélites, escribe "satellite space". Si habla del sol, escribe "sun sky".
    
    METADATOS:
    - Plataforma recomendada: "YouTube".
    - Título adictivo (máx 50 caracteres).
    - Descripción persuasiva.
    - 5 hashtags virales.
    - CTA final.

    DEBES responder ÚNICAMENTE con un JSON válido, sin markdown, con esta estructura:
    {{
      "plataforma": "YouTube",
      "titulo": "Título adictivo",
      "descripcion": "Descripción persuasiva.",
      "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5",
      "cta_link": "Link o frase final",
      "escenas": [
        {{"texto": "Gancho matemático real", "visual": "pyramid egypt"}},
        {{"texto": "Dato real 1", "visual": "math compass"}},
        {{"texto": "Dato real 2", "visual": "stone blocks"}},
        {{"texto": "Dato real 3", "visual": "stars sky"}},
        {{"texto": "Dato real 4", "visual": "map coordinates"}},
        {{"texto": "Dato real 5", "visual": "sun light"}},
        {{"texto": "Dato real 6", "visual": "satellite space"}},
        {{"texto": "Dato real 7", "visual": "ancient scroll"}},
        {{"texto": "Dato real 8", "visual": "desert sand"}},
        {{"texto": "Revelación 1", "visual": "egypt sphinx"}},
        {{"texto": "Revelación 2", "visual": "microscope science"}},
        {{"texto": "CTA final", "visual": "camera lens"}}
      ]
    }}
    """
    
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5, # Bajamos la temperatura para que sea más preciso y menos creativo
        "response_format": {"type": "json_object"}
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = content.replace("```json", "").replace("```", "").strip()
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx != -1 and end_idx != 0:
            content = content[start_idx:end_idx]
        return json.loads(content)
    except Exception as e:
        log.error(f"[GROQ] Error: {e}")
        error_texto = content[:300] if 'content' in locals() else "No hay texto"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": f"❌ *Groq Error:* {str(e)}\n\n*Texto:*\n{error_texto}"})
        return None

def disparar_github(escenas, metadata):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    payload = {"event_type": "render_video", "client_payload": {"scenes": escenas, "metadata": metadata}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r.status_code == 204
    except: return False

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

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V44.0"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, "Los secretos matemáticos de la Gran Pirámide", "datos curiosos")
    return {"status": "ACCEPTED"}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho)
    return {"status": "ACCEPTED"}
