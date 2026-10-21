import os
import logging
import asyncio
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

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

GROQ_MODEL = "openai/gpt-oss-120b"
app = FastAPI(title="Nexus Engine // Full Auto")

# -----------------------------------------------------------------------------
# 1. GENERAR GUION CON GROQ
# -----------------------------------------------------------------------------
def generar_guion(tema: str) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
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
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"Error Groq: {e}")
        return None

# -----------------------------------------------------------------------------
# 2. GENERAR VOZ (Edge-TTS)
# -----------------------------------------------------------------------------
async def generar_voz(texto: str, output_file: str):
    # Voz en español de España (Puedes cambiarla a "es-MX-JorgeNeural" para México)
    voice = "es-ES-AlvaroNeural" 
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(output_file)

# -----------------------------------------------------------------------------
# 3. BUSCAR VIDEO DE FONDO (Coverr - Sin API Key)
# -----------------------------------------------------------------------------
def obtener_video_fondo(query: str) -> str:
    # Usamos la API pública de Coverr que no requiere registro
    url = f"https://api.coverr.co/videos?query={query}&per_page=1&orientation=portrait"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            videos = data.get("hits", [])
            if videos:
                urls = videos[0].get("urls", {})
                # Priorizamos la descarga directa MP4
                video_url = urls.get("mp4_download") or urls.get("mp4")
                if video_url:
                    return video_url
    except Exception as e:
        log.error(f"Error Coverr: {e}")
    
    # PLAN B: Si Coverr falla, usamos un video genérico de Mixkit
    log.warning("Coverr falló. Usando video de respaldo.")
    return "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-background-1610-large.mp4"

# -----------------------------------------------------------------------------
# 4. ENSAMBLAR VIDEO CON FFMPEG (Optimizado para poca RAM)
# -----------------------------------------------------------------------------
def ensamblar_video(video_url: str, audio_path: str, output_path: str) -> bool:
    try:
        log.info("Descargando video de fondo...")
        video_bg = "bg.mp4"
        with open(video_bg, "wb") as f:
            f.write(requests.get(video_url, timeout=30).content)

        log.info("Ejecutando FFmpeg...")
        # Comando optimizado: -threads 1, -preset ultrafast para no colapsar Render
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", video_bg, "-i", audio_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles=subs.srt:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3'",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
            "-c:a", "aac", "-shortest", "-t", "20", output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Limpieza
        if os.path.exists(video_bg): os.remove(video_bg)
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"FFmpeg falló: {e.stderr.decode()[:500]}")
        return False
    except Exception as e:
        log.error(f"Error ensamblando: {e}")
        return False

# -----------------------------------------------------------------------------
# 5. ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus Full Auto v2", "video_source": "Coverr"}

@app.post("/generar-tendencias")
async def generar_todo():
    try:
        tema = "Misterios del océano" # Tema por defecto para pruebas
        
        # 1. Guion
        log.info("[1/5] Generando guion...")
        guion = generar_guion(tema)
        if not guion: 
            return JSONResponse(status_code=500, content={"status": "ERROR", "detail": "Fallo al generar guion"})

        # 2. Voz
        log.info("[2/5] Generando voz...")
        audio_path = "voice.mp3"
        await generar_voz(guion, audio_path)

        # 3. Fondo
        log.info("[3/5] Buscando video de fondo...")
        video_url = obtener_video_fondo("ocean mysteries")
        if not video_url: 
            return JSONResponse(status_code=500, content={"status": "ERROR", "detail": "No hay video de fondo"})

        # 4. Subtítulos SRT (Para que FFmpeg los queme en el video)
        log.info("[4/5] Generando subtítulos...")
        with open("subs.srt", "w", encoding="utf-8") as f:
            # Dividimos el texto en bloques para que los subtítulos fluyan
            f.write(f"1\n00:00:00,000 --> 00:00:20,000\n{guion}\n")

        # 5. Ensamblar
        log.info("[5/5] Ensamblando video final...")
        video_final = "video_final.mp4"
        exito = ensamblar_video(video_url, audio_path, video_final)
        if not exito: 
            return JSONResponse(status_code=500, content={"status": "ERROR", "detail": "Fallo al ensamblar el video (Posible falta de RAM)"})

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
        
        # Limpieza de archivos temporales
        for f in [audio_path, video_final, "subs.srt"]:
            if os.path.exists(f): os.remove(f)

        return {"status": "SUCCESS", "message": "Video enviado a Telegram", "guion": guion}

    except Exception as e:
        log.error(f"Error crítico en el pipeline: {e}")
        return JSONResponse(status_code=500, content={"status": "ERROR", "detail": str(e)})
