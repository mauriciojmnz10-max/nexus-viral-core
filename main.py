import os
import logging
import asyncio
import edge_tts
import requests
import subprocess
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus")

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
PEXELS_API_KEY = (os.getenv("PEXELS_API_KEY") or "").strip()

GROQ_MODEL = "openai/gpt-oss-120b"
app = FastAPI(title="Nexus Engine // Full Auto")

# 1. GENERAR GUION
def generar_guion(tema):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = (
        f"Genera un guion para un video viral de TikTok sobre: '{tema}'. "
        "Estructura: GANCHO (1 frase), CUERPO (3 frases cortas), CTA (1 frase). "
        "El texto total no debe superar las 60 palabras. No uses markdown."
    )
    payload = {"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 300}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=20)
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"Error Groq: {e}")
        return None

# 2. GENERAR VOZ (Edge-TTS)
async def generar_voz(texto, output_file):
    voice = "es-ES-AlvaroNeural" # Voz de hombre en español
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(output_file)

# 3. BUSCAR VIDEO DE FONDO (Pexels)
def obtener_video_fondo(query):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        videos = r.json().get("videos", [])
        if videos:
            return videos[0]["video_files"][0]["link"] # Link del video en HD
    except Exception as e:
        log.error(f"Error Pexels: {e}")
    return None

# 4. ENSAMBLAR VIDEO CON FFMPEG (Optimizado para poca RAM)
def ensamblar_video(video_url, audio_path, output_path):
    try:
        # Descargar el video de fondo
        video_bg = "bg.mp4"
        with open(video_bg, "wb") as f:
            f.write(requests.get(video_url).content)

        # Comando FFmpeg para recortar el video a 15s, poner el audio y quemar subtítulos simples
        # Usamos -threads 1 para no colapsar los 512MB de RAM de Render
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", video_bg, "-i", audio_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles=subs.srt:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3'",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
            "-c:a", "aac", "-shortest", "-t", "20", output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        log.error(f"Error FFmpeg: {e}")
        return False

@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus Full Auto"}

@app.post("/generar-tendencias")
async def generar_todo():
    try:
        tema = "Misterios del océano" # Puedes cambiarlo o recibirlo por parámetro
        
        # 1. Guion
        log.info("Generando guion...")
        guion = generar_guion(tema)
        if not guion: raise Exception("Fallo al generar guion")

        # 2. Voz
        log.info("Generando voz...")
        audio_path = "voice.mp3"
        await generar_voz(guion, audio_path)

        # 3. Fondo
        log.info("Buscando video de fondo...")
        video_url = obtener_video_fondo(tema)
        if not video_url: raise Exception("No se encontró video en Pexels")

        # 4. Subtítulos SRT
        with open("subs.srt", "w", encoding="utf-8") as f:
            f.write(f"1\n00:00:00,000 --> 00:00:20,000\n{guion}\n")

        # 5. Ensamblar
        log.info("Ensamblando video final...")
        video_final = "video_final.mp4"
        exito = ensamblar_video(video_url, audio_path, video_final)
        if not exito: raise Exception("Fallo al ensamblar el video")

        # 6. Enviar a Telegram
        log.info("Enviando a Telegram...")
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
        with open(video_final, "rb") as video:
            r = requests.post(telegram_url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎬 *NEXUS FULL AUTO* 🎬\n\n{guion[:100]}..."}, files={"video": video})
        
        return {"status": "SUCCESS", "message": "Video enviado a Telegram"}

    except Exception as e:
        log.error(f"Error crítico: {e}")
        return JSONResponse(status_code=500, content={"status": "ERROR", "detail": str(e)})
