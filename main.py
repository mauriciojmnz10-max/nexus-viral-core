import os
import json
import logging
import requests
import random
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

app = FastAPI(title="Nexus V49.0 // High CPM")

# LISTA DE NICHO DE ALTO CPM Y FÁCILES DE ILUSTRAR
NICHOS_ALTO_VALOR = [
    "Finanzas personales e inversión",
    "Tecnología y gadgets",
    "Inteligencia Artificial y software",
    "Educación financiera",
    "Seguros y protección de patrimonio",
    "Derecho y legal básico",
    "Ciencia y descubrimientos",
    "Productividad y hábitos"
]

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "auto"

def generar_guion(tema: str, nicho: str):
    log.info(f"[GROQ] Generando guion para: {tema} (Nicho: {nicho})")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    prompt = f"""
    Actúa como un Educador y Experto en {nicho} para YouTube Shorts.
    Genera un guion de 12 escenas sobre: '{tema}'.
    
    ESTRUCTURA NARRATIVA (ALTO VALOR Y RETENCIÓN):
    1. GANCHO (Escena 1): Plantea un error común, una pérdida de dinero o un dato impactante. (Ej: "El 90% de la gente comete este error con su tarjeta de crédito...").
    2. DESARROLLO (Escenas 2-10): Explicación paso a paso, revelación de secretos de la industria o datos técnicos. Frases cortas, usa comas.
    3. CIERRE (Escenas 11-12): Recomendación práctica y llamado a la acción (ej: "Guarda este video para no olvidarlo").
    
    REGLAS VISUALES (CRÍTICO):
    Para el campo "visual", escribe EXACTAMENTE 2 o 3 palabras clave en INGLÉS que representen el objeto FÍSICO exacto de la escena.
    Ejemplo: Si habla de dinero, pon "money cash". Si habla de tecnología, pon "laptop technology". Si habla de invertir, pon "stock market graph".
    NO uses conceptos abstractos.

    METADATOS:
    - Plataforma: "YouTube".
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
        {{"texto": "Gancho de error real", "visual": "money cash"}},
        {{"texto": "Consecuencia 1", "visual": "credit card"}},
        {{"texto": "Dato técnico 1", "visual": "stock market graph"}},
        {{"texto": "Consecuencia 2", "visual": "laptop technology"}},
        {{"texto": "Dato técnico 2", "visual": "bank building"}},
        {{"texto": "Consecuencia 3", "visual": "calculator math"}},
        {{"texto": "Dato técnico 3", "visual": "smartphone app"}},
        {{"texto": "Consecuencia 4", "visual": "person working"}},
        {{"texto": "Dato técnico 4", "visual": "graph finance"}},
        {{"texto": "Revelación final", "visual": "business meeting"}},
        {{"texto": "Pregunta de debate", "visual": "question mark"}},
        {{"texto": "CTA y suscripción", "visual": "subscribe button"}}
      ]
    }}
    """
    
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "response_format": {"type": "json_object"}
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = content.replace("```json", "").replace("```", "").strip()
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx != -1 and end_idx != 0: content = content[start_idx:end_idx]
        return json.loads(content)
    except Exception as e:
        log.error(f"[GROQ] Error: {e}")
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": f"❌ *Groq Error:* {str(e)}"})
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
    # Si el nicho es "auto", selecciona uno al azar de la lista de alto CPM
    if nicho == "auto":
        nicho = random.choice(NICHOS_ALTO_VALOR)
        log.info(f"[AUTO] Nicho seleccionado: {nicho}")

    data = generar_guion(tema, nicho)
    if not data: return
    escenas = data.get("escenas", [])
    metadata = {
        "plataforma": data.get("plataforma", "YouTube"),
        "titulo": data.get("titulo", "Video"),
        "descripcion": data.get("descripcion", ""),
        "hashtags": data.get("hashtags", ""),
        "cta_link": data.get("cta_link", ""),
        "nicho_usado": nicho # Guardamos el nicho para mostrarlo en Telegram
    }
    if disparar_github(escenas, metadata):
        msg = f"🚀 *NEXUS HÍBRIDO* 🚀\n\nSe ha enviado el guion a GitHub Actions.\n\n📌 *Título:* {metadata['titulo']}\n📊 *Nicho:* {nicho}\n\n*El video llegará a este chat en unos minutos.*"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V49.0"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    # Tema por defecto para el Cron
    background_tasks.add_task(procesar_video_en_segundo_plano, "El error financiero que te hace perder dinero", "auto")
    return {"status": "ACCEPTED"}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho)
    return {"status": "ACCEPTED"}
