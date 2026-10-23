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

app = FastAPI(title="Nexus V51.0 // Rotation & Hybrid")

# --- SISTEMA DE ROTACIÓN DE CONTENIDO ---
TEMAS_FINANZAS = ["El error de las tarjetas de crédito", "Cómo ahorrar sin darte cuenta", "La trampa de los préstamos rápidos"]
TEMAS_TECNOLOGIA = ["La IA que te quitará el trabajo", "El gadget que ahorra energía", "Cómo proteger tu privacidad en internet"]
TEMAS_MISTERIO = ["El secreto de la Gran Pirámide", "Las coordenadas del Triángulo de las Bermudas", "El código oculto en la Mona Lisa"]
QUIZ_CULTURA = ["Quiz: ¿Cuánto sabes de historia universal?", "Quiz: Adivina el país por su bandera", "Quiz: Preguntas de ciencia básica"]

def obtener_tema_aleatorio():
    categorias = ["finanzas", "tecnologia", "misterio", "quiz"]
    categoria = random.choice(categorias)
    
    if categoria == "finanzas":
        return random.choice(TEMAS_FINANZAS), "finanzas", "normal"
    elif categoria == "tecnologia":
        return random.choice(TEMAS_TECNOLOGIA), "tecnologia", "normal"
    elif categoria == "misterio":
        return random.choice(TEMAS_MISTERIO), "misterio", "normal"
    else:
        return random.choice(QUIZ_CULTURA), "cultura general", "quiz"

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "auto"
    modo: str = "normal"

def generar_guion(tema: str, nicho: str, modo: str):
    log.info(f"[GROQ] Generando guion para: {tema} (Modo: {modo})")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    if modo == "quiz":
        prompt = f"""
        Actúa como un creador de contenido de entretenimiento para YouTube Shorts.
        Genera un guion tipo QUIZ de 12 escenas sobre: '{tema}'.
        
        ESTRUCTURA:
        1. GANCHO: "Solo el 1% puede responder esto..."
        2. Pregunta 1 (Escena 2) y Respuesta 1 (Escena 3).
        3. Pregunta 2 (Escena 4) y Respuesta 2 (Escena 5).
        4. Pregunta 3 (Escena 6) y Respuesta 3 (Escena 7).
        5. Cierre: "¿Cuántas acertaste? Comenta tu puntuación".
        
        REGLAS VISUALES:
        Para el campo "visual", escribe 2 palabras clave en INGLÉS relacionadas con el tema o con "question mark", "brain".
        """
    else:
        prompt = f"""
        Actúa como un Educador y Experto en {nicho} para YouTube Shorts.
        Genera un guion de 12 escenas sobre: '{tema}'.
        
        ESTRUCTURA NARRATIVA:
        1. GANCHO: Plantea un error, pérdida o dato impactante.
        2. DESARROLLO: Explicación paso a paso.
        3. CIERRE: Recomendación y CTA.
        
        REGLAS VISUALES:
        Escribe 2 palabras clave en INGLÉS del objeto físico. (Ej: "money cash", "laptop technology").
        """

    prompt += """
    METADATOS: Título adictivo, descripción, 5 hashtags, CTA.
    DEBES responder ÚNICAMENTE con un JSON válido, sin markdown, con esta estructura:
    {
      "plataforma": "YouTube",
      "titulo": "Título adictivo",
      "descripcion": "Descripción.",
      "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5",
      "cta_link": "CTA",
      "escenas": [
        {"texto": "Texto de la escena", "visual": "keyword"}
      ]
    }
    (Asegúrate de generar 12 escenas)
    """
    
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
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

def procesar_video_en_segundo_plano(tema: str, nicho: str, modo: str = "normal"):
    data = generar_guion(tema, nicho, modo)
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
    if disparar_github(escenas, metadata):
        msg = f"🚀 *NEXUS HÍBRIDO* 🚀\n\nSe ha enviado el guion a GitHub Actions.\n\n📌 *Título:* {metadata['titulo']}\n📊 *Nicho:* {nicho} ({modo})\n\n*El video llegará a este chat en unos minutos.*"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V51.0"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    tema, nicho, modo = obtener_tema_aleatorio()
    background_tasks.add_task(procesar_video_en_segundo_plano, tema, nicho, modo)
    return {"status": "ACCEPTED", "tema": tema}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho, request.modo)
    return {"status": "ACCEPTED"}
