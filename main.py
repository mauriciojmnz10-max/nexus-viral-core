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

app = FastAPI(title="Nexus V55.0 // Cinematic Shield")

# --- POOL DE TEMAS MASIVO Y VARIADO ---
TEMAS_POOL = [
    # Finanzas
    {"tema": "El error de las tarjetas de crédito", "nicho": "finanzas", "modo": "normal"},
    {"tema": "Cómo ahorrar sin darte cuenta", "nicho": "finanzas", "modo": "normal"},
    {"tema": "La trampa de los préstamos rápidos", "nicho": "finanzas", "modo": "normal"},
    {"tema": "El interés compuesto explicado en 60s", "nicho": "finanzas", "modo": "normal"},
    {"tema": "Por qué los ricos no tienen deudas", "nicho": "finanzas", "modo": "normal"},
    # Tecnología / IA
    {"tema": "La IA que te quitará el trabajo", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "El gadget que ahorra energía", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "Cómo proteger tu privacidad en internet", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "El futuro de los coches autónomos", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "La verdad sobre el 5G", "nicho": "tecnologia", "modo": "normal"},
    # Legal / Derecho
    {"tema": "Tus derechos si te detiene la policía", "nicho": "legal", "modo": "normal"},
    {"tema": "El error legal al firmar un contrato", "nicho": "legal", "modo": "normal"},
    {"tema": "Cómo reclamar una multa injusta", "nicho": "legal", "modo": "normal"},
    # Salud / Bienestar
    {"tema": "El hábito que destruye tu sueño", "nicho": "salud", "modo": "normal"},
    {"tema": "Por qué el azúcar oculto te enferma", "nicho": "salud", "modo": "normal"},
    {"tema": "La verdad sobre las dietas milagro", "nicho": "salud", "modo": "normal"},
    # Psicología Oscura
    {"tema": "Cómo manipulan tu mente los anuncios", "nicho": "psicologia", "modo": "normal"},
    {"tema": "El sesgo cognitivo que te hace gastar", "nicho": "psicologia", "modo": "normal"},
    {"tema": "La técnica de persuasión de la CIA", "nicho": "psicologia", "modo": "normal"},
    # Motivación / Éxito
    {"tema": "La regla de los 5 segundos para vencer la pereza", "nicho": "motivacion", "modo": "normal"},
    {"tema": "Cómo levantarte a las 5 AM sin morir", "nicho": "motivacion", "modo": "normal"},
    {"tema": "El secreto de los estoicos para ser feliz", "nicho": "motivacion", "modo": "normal"},
    # Historia / Crímenes
    {"tema": "El secreto oculto de la Gran Muralla China", "nicho": "historia", "modo": "normal"},
    {"tema": "El crimen que cambió la historia de Roma", "nicho": "historia", "modo": "normal"},
    {"tema": "La verdad sobre Jack el Destripador", "nicho": "historia", "modo": "normal"},
    # Misterio / Ciencia
    {"tema": "El código oculto en la Mona Lisa", "nicho": "misterio", "modo": "normal"},
    {"tema": "El Triángulo de las Bermudas: la verdad", "nicho": "misterio", "modo": "normal"},
    {"tema": "¿Qué hay dentro de un agujero negro?", "nicho": "ciencia", "modo": "normal"},
    {"tema": "El experimento de la prisión de Stanford", "nicho": "ciencia", "modo": "normal"},
    # Quiz (Cultura, Ciencia, Cine, etc.)
    {"tema": "Quiz: ¿Cuánto sabes de historia universal?", "nicho": "cultura general", "modo": "quiz"},
    {"tema": "Quiz: Adivina el país por su bandera", "nicho": "geografia", "modo": "quiz"},
    {"tema": "Quiz: Preguntas de ciencia básica", "nicho": "ciencia", "modo": "quiz"},
    {"tema": "Quiz: ¿Cuánto sabes de cine?", "nicho": "cine", "modo": "quiz"},
    {"tema": "Quiz: Preguntas de cultura pop", "nicho": "cultura pop", "modo": "quiz"},
    {"tema": "Quiz: Matemáticas rápidas", "nicho": "matematicas", "modo": "quiz"}
]

# Cola global que se vacía y se rellena
COLA_TEMAS = []

def obtener_tema_aleatorio():
    global COLA_TEMAS
    if not COLA_TEMAS:
        COLA_TEMAS = TEMAS_POOL.copy()
        random.shuffle(COLA_TEMAS)
        log.info("[ROTACIÓN] Cola de temas rellenada y desordenada.")
    
    seleccion = COLA_TEMAS.pop(0)
    log.info(f"[ROTACIÓN] Tema seleccionado: {seleccion['tema']}")
    return seleccion["tema"], seleccion["nicho"], seleccion["modo"]

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
        Genera un guion tipo QUIZ de 8 escenas sobre: '{tema}'.
        
        ESTRUCTURA (OBLIGATORIA):
        1. GANCHO: "Solo el 1% puede responder esto..."
        2. Pregunta 1 (Escena 2): Escribe la pregunta y las 3 opciones en el mismo texto. (Ej: "¿Cuál es el planeta rojo? A) Venus B) Marte C) Júpiter").
        3. Respuesta 1 (Escena 3): Solo el texto de la respuesta correcta y una breve explicación.
        4. Pregunta 2 (Escena 4) y Respuesta 2 (Escena 5).
        5. Pregunta 3 (Escena 6) y Respuesta 3 (Escena 7).
        6. Cierre (Escena 8): "¿Cuántas acertaste? Comenta tu puntuación".
        
        REGLAS VISUALES:
        Para el campo "visual", escribe 2 palabras clave en INGLÉS (ej. "question mark", "brain", "science").
        """
    else:
        prompt = f"""
        Actúa como un Educador y Experto en {nicho} para YouTube Shorts.
        Genera un guion de 12 escenas sobre: '{tema}'.
        
        ESTRUCTURA:
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
    return {"status": "ONLINE", "engine": "Nexus V55.0"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    tema, nicho, modo = obtener_tema_aleatorio()
    background_tasks.add_task(procesar_video_en_segundo_plano, tema, nicho, modo)
    return {"status": "ACCEPTED", "tema": tema}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho, request.modo)
    return {"status": "ACCEPTED"}
