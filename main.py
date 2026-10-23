import os
import json
import logging
import requests
import uuid
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
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

app = FastAPI(title="Nexus V31.0 // Hybrid Brain")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "drama"

def generar_guion(tema, nicho):
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}", "Content-Type": "application/json", "User-Agent": "curl/8.0.1"}
    prompt = f"""Actúa como Guionista Senior de Dramabox. Genera un guion de 14 escenas sobre '{tema}', tono {nicho}. Reglas: Gancho impactante, ritmo rápido, 12-15 palabras por escena. Metadatos: plataforma (YouTube), título, descripción, hashtags, cta. JSON: {{"plataforma":"YouTube", "titulo":"...", "descripcion":"...", "hashtags":"...", "cta_link":"...", "escenas":[{{"texto":"...","visual":"keyword"}}]}}"""
    payload = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.85, "response_format": {"type": "json_object"}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=45)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log.error(f"Error Groq: {e}")
        return None

def disparar_github(escenas, metadata):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    payload = {"event_type": "render_video", "client_payload": {"scenes": escenas, "metadata": metadata}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r.status_code == 204
    except: return False

@app.post("/generar-tendencias")
async def generar(background_tasks: BackgroundTasks):
    tema = "El secreto de la Gran Pirámide"
    nicho = "drama"
    background_tasks.add_task(procesar, tema, nicho)
    return {"status": "ACCEPTED", "message": "Enviado a GitHub Actions."}

def procesar(tema, nicho):
    raw_json = generar_guion(tema, nicho)
    if not raw_json: return
    data = json.loads(raw_json)
    escenas = data.get("escenas", [])
    metadata = {"plataforma": data.get("plataforma"), "titulo": data.get("titulo"), "descripcion": data.get("descripcion"), "hashtags": data.get("hashtags"), "cta_link": data.get("cta_link")}
    
    if disparar_github(escenas, metadata):
        msg = f"🚀 *NEXUS HÍBRIDO* 🚀\n\nSe ha enviado el guion a GitHub Actions.\n\n📌 *Título:* {metadata['titulo']}\n🎯 *Plataforma:* {metadata['plataforma']}\n\n*El video llegará a este chat en unos minutos.*"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    else:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": "❌ Error al conectar con GitHub Actions."})
