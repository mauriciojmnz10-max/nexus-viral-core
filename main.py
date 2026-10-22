import os
import json
import logging
import edge_tts
import requests
import subprocess
import shutil
import asyncio
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus")

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

CF_ACCOUNT_ID = "ead76709dc92c64a480ffca88bbc1b29"
CF_GATEWAY_ID = "i-a" 
CF_AUTH_TOKEN = (os.getenv("CF_AUTH_TOKEN") or "").strip()

WORK_DIR = "/tmp/nexus_work"
app = FastAPI(title="Nexus V3.5 Engine // Audio Validator")

# =============================================================================
# 1. GENERACIÓN DE GUION
# =============================================================================
def generar_guion_estructurado(tema: str) -> list:
    log.info(f"[GROQ] Generando JSON por escenas para: {tema}")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.1"
    }
    
    prompt = f"""
    Genera un guion para un video viral de TikTok sobre: '{tema}'.
    DEBES responder ÚNICAMENTE con un JSON válido, sin markdown, con esta estructura exacta:
    {{
      "escenas": [
        {{"texto": "Frase del gancho (máx 10 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Punto 1 del cuerpo (máx 12 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Punto 2 del cuerpo (máx 12 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Frase del CTA (máx 10 palabras)", "visual": "english prompt for stock video"}}
      ]
    }}
    """
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"]).get("escenas", [])
    except Exception as e:
        log.error(f"[GROQ] Error: {e}")
        return []

# =============================================================================
# 2. VOZ, VALIDACIÓN Y CONVERSIÓN
# =============================================================================
def es_audio_valido(filepath: str) -> bool:
    """Usa ffprobe para verificar que el archivo de audio es legible y tiene duración."""
    if not os.path.exists(filepath) or os.path.getsize(filepath) < 100:
        return False
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False
        duracion = float(result.stdout.strip())
        return duracion > 0.5
    except Exception:
        return False

async def generar_audio_escena(texto: str, output_file: str):
    log.info(f"[TTS] Generando audio para: {texto[:30]}...")
    
    temp_mp3 = output_file.replace(".wav", "_temp.mp3")
    try:
        communicate = edge_tts.Communicate(texto, "es-ES-AlvaroNeural")
        await communicate.save(temp_mp3)
    except Exception as e:
        log.error(f"[TTS] Edge-TTS falló directamente: {e}")
        temp_mp3 = None

    # Validar el MP3 generado por edge-tts
    if temp_mp3 and es_audio_valido(temp_mp3):
        try:
            # Convertir a WAV para limpiar el archivo
            cmd = ["ffmpeg", "-y", "-i", temp_mp3, "-ar", "44100", "-ac", "2", output_file]
            subprocess.run(cmd, check=True, capture_output=True, timeout=15)
            log.info(f"[TTS] Audio convertido a WAV correctamente.")
            
            # Limpiamos el MP3 temporal
            if os.path.exists(temp_mp3): os.remove(temp_mp3)
            return True
        except Exception as e:
            log.error(f"[TTS] Fallo al convertir MP3 a WAV: {e}")

    # Si falló, generar silencio de respaldo
    log.warning("[TTS] El audio original no es válido. Generando silencio de respaldo.")
    if temp_mp3 and os.path.exists(temp_mp3):
        try: os.remove(temp_mp3)
        except: pass
        
    try:
        cmd_fallback = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "3", "-acodec", "pcm_s16le", output_file
        ]
        subprocess.run(cmd_fallback, check=True, capture_output=True)
        return True
    except Exception as fallback_error:
        log.error(f"[TTS] Incluso el respaldo falló: {fallback_error}")
        return False

def obtener_duracion_audio(filepath: str) -> float:
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 3.0

# =============================================================================
# 3. DESCARGA DE CLIPS
# =============================================================================
def descargar_clip_vertical(query: str, output_file: str):
    try:
        url = f"https://api.coverr.co/videos?query={query}&per_page=1&orientation=portrait"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                video_url = hits[0].get("urls", {}).get("mp4_download") or hits[0].get("urls", {}).get("mp4")
                if video_url:
                    with open(output_file, "wb") as f:
                        f.write(requests.get(video_url, timeout=20).content)
                    return True
    except Exception:
        pass
    # Fallback
    try:
        with open(output_file, "wb") as f:
            f.write(requests.get("https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-background-1610-large.mp4", timeout=20).content)
        return True
    except Exception as e:
        log.error(f"[STOCK] Fallo total: {e}")
        return False

# =============================================================================
# 4. ENSAMBLAJE Y SUBTÍTULOS
# =============================================================================
def procesar_escena_video(audio: str, video: str, output: str, duracion: float):
    try:
        cmd = [
            "ffmpeg", "-y", 
            "-err_detect", "ignore_err", 
            "-fflags", "+discardcorrupt",
            "-stream_loop", "-1", "-i", video, 
            "-i", audio,
            "-t", str(duracion),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
            "-c:a", "aac", "-shortest", output
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"[FFMPEG] Error escena: {e.stderr.decode()[:300]}")
        return False

def concatenar_y_subtitular(lista_videos: list, escenas: list, output_final: str):
    try:
        srt_file = os.path.join(WORK_DIR, "subs.srt")
        current_time = 0.0
        with open(srt_file, "w", encoding="utf-8") as f:
            for i, escena in enumerate(escenas):
                duracion_estimada = max(2.0, len(escena["texto"].split()) / 2.5)
                start, end = current_time, current_time + duracion_estimada
                
                def format_time(sec):
                    h, m, s = int(sec//3600), int((sec%3600)//60), int(sec%60)
                    ms = int((sec - int(sec)) * 1000)
                    return f"{h:02}:{m:02}:{s:02},{ms:03}"
                
                f.write(f"{i+1}\n{format_time(start)} --> {format_time(end)}\n{escena['texto']}\n\n")
                current_time = end

        concat_file = os.path.join(WORK_DIR, "concat.txt")
        with open(concat_file, "w") as f:
            for vid in lista_videos:
                f.write(f"file '{vid}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-vf", f"subtitles={srt_file}:force_style='FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3'",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
            "-c:a", "aac", output_final
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        log.error(f"[FFMPEG] Error concat: {e}")
        return False

# =============================================================================
# 5. LÓGICA DE FONDO
# =============================================================================
def procesar_video_en_segundo_plano(tema: str):
    try:
        escenas = generar_guion_estructurado(tema)
        if not escenas:
            log.error("[BG] Guion vacío.")
            return

        videos_procesados = []
        for i, escena in enumerate(escenas):
            log.info(f"[BG] Escena {i+1}/{len(escenas)}...")
            
            audio_path = os.path.join(WORK_DIR, f"audio_{i}.wav")
            video_bg = os.path.join(WORK_DIR, f"bg_{i}.mp4")
            scene_out = os.path.join(WORK_DIR, f"scene_{i}.mp4")

            await asyncio.to_thread(asyncio.run, generar_audio_escena(escena["texto"], audio_path))
            duracion = obtener_duracion_audio(audio_path)
            
            if not descargar_clip_vertical(escena["visual"], video_bg):
                log.error(f"[BG] Fallo stock escena {i+1}")
                continue

            if not procesar_escena_video(audio_path, video_bg, scene_out, duracion):
                log.error(f"[BG] Fallo FFmpeg escena {i+1}")
                continue
            
            videos_procesados.append(scene_out)

        if not videos_procesados:
            log.error("[BG] No se procesó ningún video.")
            return

        log.info("[BG] Concatenando...")
        video_final = os.path.join(WORK_DIR, "final.mp4")
        if not concatenar_y_subtitular(videos_procesados, escenas, video_final):
            log.error("[BG] Fallo concatenación final.")
            return

        log.info("[BG] Enviando a Telegram...")
        with open(video_final, "rb") as video:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", 
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎬 *NEXUS V3.5* 🎬\n\n{tema}"}, 
                files={"video": video},
                timeout=120
            )
        log.info("[BG] ¡Video enviado!")

    except Exception as e:
        log.error(f"[BG] ERROR: {e}")
    finally:
        if os.path.exists(WORK_DIR): shutil.rmtree(WORK_DIR)

# =============================================================================
# 6. ENDPOINT PRINCIPAL
# =============================================================================
@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V3.5"}

@app.post("/generar-tendencias")
async def generar_video_completo(background_tasks: BackgroundTasks):
    if os.path.exists(WORK_DIR):
        shutil.rmtree(WORK_DIR)
    os.makedirs(WORK_DIR, exist_ok=True)
    
    tema = "Secretos del universo"
    
    background_tasks.add_task(procesar_video_en_segundo_plano, tema)
    
    return {"status": "ACCEPTED", "message": "Video en proceso. Revisa Telegram en 1 minuto."}
