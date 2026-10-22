import os
import logging
import edge_tts
import requests
import subprocess
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus")

# Credenciales principales
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

# Cloudflare AI Gateway (Ya configurado con tus datos)
CF_ACCOUNT_ID = "ead76709dc92c64a480ffca88bbc1b29"
CF_GATEWAY_ID = "i-a" 
CF_AUTH_TOKEN = (os.getenv("CF_AUTH_TOKEN") or "").strip()

GROQ_MODEL = "openai/gpt-oss-120b"
app = FastAPI(title="Nexus Engine // Gateway")

# -----------------------------------------------------------------------------
# 1. GENERAR GUION CON GROQ (Vía Cloudflare)
# -----------------------------------------------------------------------------
def generar_guion(tema: str) -> str:
    log.info(f"[GROQ] Iniciando petición para: {tema}")
    if not GROQ_API_KEY:
        log.error("[GROQ] API Key está vacía.")
        return None
        
    # URL del Gateway de Cloudflare
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.1" # Evita el bloqueo por WAF
    }
    
    prompt = (
        f"Genera un guion para un video viral de TikTok sobre: '{tema}'. "
        "Estructura: GANCHO (1 frase), CUERPO (3 frases cortas), CTA (1 frase). "
        "El texto total no debe superar las 60 palabras. No uses markdown, ni asteriscos, ni guiones bajos."
    )
    payload = {
        "model": GROQ_MODEL, 
        "messages": [{"role": "user", "content": prompt}], 
        "max_tokens": 300,
        "temperature": 0.8
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=40)
        if r.status_code != 200:
            log.error(f"[GROQ] Error {r.status_code}: {r.text}")
            return None
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"[GROQ] Excepción: {e}")
        return None

# -----------------------------------------------------------------------------
# 2. GENERAR VOZ (Edge-TTS)
# -----------------------------------------------------------------------------
async def generar_voz(texto: str, output_file: str):
    log.info("[TTS] Generando voz con Edge-TTS...")
    try:
        voice = "es-ES-AlvaroNeural" 
        communicate = edge_tts.Communicate(texto, voice)
        await communicate.save(output_file)
        log.info("[TTS] Voz generada OK.")
    except Exception as e:
        log.error(f"[TTS] Error: {e}")

# -----------------------------------------------------------------------------
# 3. BUSCAR VIDEO DE FONDO (Coverr)
# -----------------------------------------------------------------------------
def obtener_video_fondo(query: str) -> str:
    log.info(f"[VIDEO] Buscando fondo para: {query}")
    try:
        url = f"https://api.coverr.co/videos?query={query}&per_page=1&orientation=portrait"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            videos = r.json().get("hits", [])
            if videos:
                urls = videos[0].get("urls", {})
                video_url = urls.get("mp4_download") or urls.get("mp4")
                if video_url:
                    log.info(f"[VIDEO] Encontrado en Coverr.")
                    return video_url
    except Exception as e:
        log.warning(f"[VIDEO] Coverr falló: {e}")
    
    # Plan B: Video de respaldo
    log.warning("[VIDEO] Usando video de respaldo (Mixkit).")
    return "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-background-1610-large.mp4"

# -----------------------------------------------------------------------------
# 4. ENSAMBLAR VIDEO CON FFMPEG
# -----------------------------------------------------------------------------
def ensamblar_video(video_url: str, audio_path: str, output_path: str) -> bool:
    try:
        log.info("[FFMPEG] Descargando video de fondo...")
        video_bg = "bg.mp4"
        with open(video_bg, "wb") as f:
            f.write(requests.get(video_url, timeout=30).content)

        log.info("[FFMPEG] Ejecutando montaje...")
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", video_bg, "-i", audio_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles=subs.srt:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3'",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
            "-c:a", "aac", "-shortest", "-t", "20", output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(video_bg): os.remove(video_bg)
        log.info("[FFMPEG] Video ensamblado con éxito.")
        return True
    except Exception as e:
        log.error(f"[FFMPEG] Error: {e}")
        return False

# -----------------------------------------------------------------------------
# 5. ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus Full Auto v4 (Gateway i-a)"}

@app.post("/generar-tendencias")
async def generar_todo():
    try:
        tema = "Misterios del océano"
        
        log.info("=== INICIANDO FLUJO ===")
        
        # 1. Guion
        guion = generar_guion(tema)
        if not guion: 
            raise Exception("Fallo en el paso 1 (Groq)")

        # 2. Voz
        audio_path = "voice.mp3"
        await generar_voz(guion, audio_path)

        # 3. Fondo
        video_url = obtener_video_fondo("ocean")
        
        # 4. Subtítulos
        with open("subs.srt", "w", encoding="utf-8") as f:
            f.write(f"1\n00:00:00,000 --> 00:00:20,000\n{guion}\n")

        # 5. Ensamblar
        video_final = "video_final.mp4"
        exito = ensamblar_video(video_url, audio_path, video_final)
        if not exito: 
            raise Exception("Fallo en el paso 5 (FFmpeg)")

        # 6. Enviar a Telegram
        log.info("[TELEGRAM] Enviando video final...")
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
        with open(video_final, "rb") as video:
            r = requests.post(
                telegram_url, 
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎬 *NEXUS FULL AUTO* 🎬\n\n{guion[:120]}..."}, 
                files={"video": video},
                timeout=60
            )
            if r.status_code != 200:
                log.error(f"[TELEGRAM] Error: {r.text}")
        
        for f in [audio_path, video_final, "subs.srt"]:
            if os.path.exists(f): os.remove(f)

        log.info("=== FLUJO COMPLETADO ===")
        return {"status": "SUCCESS", "message": "Video enviado"}

    except Exception as e:
        log.error(f"ERROR CRÍTICO: {e}")
        return JSONResponse(status_code=500, content={"status": "ERROR", "detail": str(e)})
