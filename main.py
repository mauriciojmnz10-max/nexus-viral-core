import os
import json
import logging
import requests
import subprocess
import shutil
import uuid
import asyncio
import edge_tts
from gtts import gTTS
from pydub import AudioSegment
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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
PIXABAY_API_KEY = (os.getenv("PIXABAY_API_KEY") or "").strip()

CF_ACCOUNT_ID = "ead76709dc92c64a480ffca88bbc1b29"
CF_GATEWAY_ID = "i-a" 
CF_AUTH_TOKEN = (os.getenv("CF_AUTH_TOKEN") or "").strip()

app = FastAPI(title="Nexus V20.0 // OOM Shield")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "misterio"

# =============================================================================
# 1. GENERACIÓN DE GUION (7 ESCENAS)
# =============================================================================
def generar_guion_estructurado(tema: str, nicho: str) -> list:
    log.info(f"[GROQ] Generando guion de 7 escenas para: {tema}")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.1"
    }
    
    prompt = f"""
    Actúa como un guionista experto en videos virales de TikTok.
    Genera un guion de 7 escenas sobre: '{tema}', con un tono de {nicho}.
    
    REGLAS:
    1. GANCHO: La primera frase debe enganchar en 3 segundos.
    2. DESARROLLO: 5 frases que cuenten una historia o datos curiosos.
    3. CIERRE: Una frase final con llamado a la acción (CTA).
    4. Cada escena debe tener entre 10 y 15 palabras para que duren más.
    
    DEBES responder ÚNICAMENTE con un JSON válido, sin markdown, con esta estructura exacta:
    {{
      "escenas": [
        {{"texto": "Gancho (máx 12 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Desarrollo 1 (máx 15 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Desarrollo 2 (máx 15 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Desarrollo 3 (máx 15 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Desarrollo 4 (máx 15 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Desarrollo 5 (máx 15 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "CTA (máx 12 palabras)", "visual": "english prompt for stock video"}}
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
# 2. VOZ (EDGE-TTS HUMANO CON FALLBACK)
# =============================================================================
async def generar_audio_edge(texto: str, output_mp3: str):
    voice = "es-ES-AlvaroNeural" 
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(output_mp3)

def generar_audio_escena(texto: str, output_wav: str) -> bool:
    log.info(f"[TTS] Generando audio para: {texto[:30]}...")
    temp_mp3 = output_wav.replace(".wav", "_temp.mp3")
    
    try:
        asyncio.run(generar_audio_edge(texto, temp_mp3))
        audio = AudioSegment.from_file(temp_mp3, format="mp3")
        audio.export(output_wav, format="wav")
        if os.path.exists(temp_mp3): os.remove(temp_mp3)
        return True
    except Exception as e:
        log.warning(f"[TTS] Edge-TTS falló: {e}. Usando gTTS.")
        if os.path.exists(temp_mp3): os.remove(temp_mp3)
        
    try:
        tts = gTTS(text=texto, lang='es', slow=False)
        tts.save(temp_mp3)
        audio = AudioSegment.from_file(temp_mp3, format="mp3")
        audio.export(output_wav, format="wav")
        if os.path.exists(temp_mp3): os.remove(temp_mp3)
        return True
    except Exception as e:
        log.error(f"[TTS] gTTS también falló: {e}. Silencio.")
        try:
            silence = AudioSegment.silent(duration=3000)
            silence.export(output_wav, format="wav")
            return True
        except Exception:
            return False

def obtener_duracion_audio(filepath: str) -> float:
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 3.0

# =============================================================================
# 3. DESCARGA DE CLIPS (PIXABAY)
# =============================================================================
def descargar_clip_vertical(query: str, output_file: str):
    if PIXABAY_API_KEY:
        try:
            url = "https://pixabay.com/api/videos/"
            params = {"key": PIXABAY_API_KEY, "q": query, "per_page": 3, "orientation": "vertical", "video_type": "film"}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                hits = r.json().get("hits", [])
                if hits:
                    videos = hits[0].get("videos", {})
                    video_url = videos.get("medium", {}).get("url") or videos.get("small", {}).get("url")
                    if video_url:
                        with open(output_file, "wb") as f:
                            f.write(requests.get(video_url, timeout=30).content)
                        return True
        except Exception:
            pass
    # Fallback
    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=1080x1920:d=10,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", output_file]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception:
        return False

# =============================================================================
# 4. ENSAMBLAJE DE VIDEO MUDO Y AUDIO MAESTRO
# =============================================================================
def procesar_escena_video_mudo(video: str, output: str, duracion: float):
    try:
        if os.path.exists(output): os.remove(output)
        cmd = [
            "ffmpeg", "-y", "-i", video, "-t", str(duracion),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-an", output
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        log.error(f"[FFMPEG] Error escena muda: {e}")
        return False

def unir_audios(audios: list, output_wav: str) -> bool:
    try:
        combined = AudioSegment.empty()
        for audio_file in audios:
            segment = AudioSegment.from_file(audio_file, format="wav")
            combined += segment
        combined.export(output_wav, format="wav")
        return True
    except Exception as e:
        log.error(f"[AUDIO] Error uniendo pistas: {e}")
        return False

# =============================================================================
# 5. CONCATENACIÓN FINAL Y SUBTÍTULOS
# =============================================================================
def concatenar_y_subtitular(lista_videos: list, escenas: list, audio_maestro: str, output_final: str, work_dir: str):
    try:
        srt_file = os.path.join(work_dir, "subs.srt")
        current_time = 0.0
        with open(srt_file, "w", encoding="utf-8") as f:
            for i, escena in enumerate(escenas):
                audio_path = os.path.join(work_dir, f"audio_{i}.wav")
                duracion_real = obtener_duracion_audio(audio_path)
                start, end = current_time, current_time + duracion_real
                
                def format_time(sec):
                    h, m, s = int(sec//3600), int((sec%3600)//60), int(sec%60)
                    ms = int((sec - int(sec)) * 1000)
                    return f"{h:02}:{m:02}:{s:02},{ms:03}"
                
                texto = escena['texto']
                if len(texto) > 18:
                    mid = len(texto) // 2
                    texto = texto[:mid] + "\n" + texto[mid:]
                
                f.write(f"{i+1}\n{format_time(start)} --> {format_time(end)}\n{texto}\n\n")
                current_time = end

        concat_file = os.path.join(work_dir, "concat.txt")
        with open(concat_file, "w") as f:
            for vid in lista_videos:
                f.write(f"file '{vid}'\n")

        if os.path.exists(output_final): os.remove(output_final)
        
        style = "FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=300"
        
        video_mudo_temp = os.path.join(work_dir, "video_mudo.mp4")
        cmd_concat = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", video_mudo_temp]
        subprocess.run(cmd_concat, check=True, capture_output=True)

        cmd_final = [
            "ffmpeg", "-y", "-i", video_mudo_temp, "-i", audio_maestro,
            "-vf", f"subtitles={srt_file}:force_style='{style}'",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
            "-c:a", "aac", "-shortest", output_final
        ]
        subprocess.run(cmd_final, check=True, capture_output=True)
        return True
    except Exception as e:
        log.error(f"[FFMPEG] Error concat final: {e}")
        return False

# =============================================================================
# 6. LÓGICA DE FONDO (OPTIMIZADA CONTRA OOM)
# =============================================================================
def procesar_video_en_segundo_plano(tema: str, nicho: str):
    work_dir = f"/tmp/nexus_{uuid.uuid4().hex}"
    os.makedirs(work_dir, exist_ok=True)
    log.info(f"[BG] Directorio de trabajo: {work_dir}")

    try:
        escenas = generar_guion_estructurado(tema, nicho)
        if not escenas:
            log.error("[BG] Guion vacío.")
            return

        videos_procesados = []
        audios_procesados = []

        for i, escena in enumerate(escenas):
            log.info(f"[BG] Escena {i+1}/{len(escenas)}...")
            
            audio_path = os.path.join(work_dir, f"audio_{i}.wav")
            video_bg = os.path.join(work_dir, f"bg_{i}.mp4")
            scene_out = os.path.join(work_dir, f"scene_{i}.mp4")

            generar_audio_escena(escena["texto"], audio_path)
            duracion = obtener_duracion_audio(audio_path)
            audios_procesados.append(audio_path)
            
            if not descargar_clip_vertical(escena.get("visual", "abstract"), video_bg):
                log.error(f"[BG] Fallo stock escena {i+1}")
                continue

            if not procesar_escena_video_mudo(video_bg, scene_out, duracion):
                log.error(f"[BG] Fallo FFmpeg escena {i+1}")
                continue
            
            videos_procesados.append(scene_out)

            # LIMPIEZA INMEDIATA PARA LIBERAR MEMORIA
            if os.path.exists(video_bg): os.remove(video_bg)

        if not videos_procesados:
            log.error("[BG] No se procesó ningún video.")
            return

        log.info("[BG] Uniendo audio maestro...")
        audio_maestro = os.path.join(work_dir, "audio_maestro.wav")
        if not unir_audios(audios_procesados, audio_maestro):
            log.error("[BG] Fallo al unir audios.")
            return

        log.info("[BG] Concatenando y subtitulando...")
        video_final = os.path.join(work_dir, "final.mp4")
        if not concatenar_y_subtitular(videos_procesados, escenas, audio_maestro, video_final, work_dir):
            log.error("[BG] Fallo concatenación final.")
            return

        log.info("[BG] Enviando a Telegram...")
        with open(video_final, "rb") as video:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", 
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎬 *NEXUS V20.0* 🎬\n\n🎯 Tema: {tema}\n🎭 Nicho: {nicho}"}, 
                files={"video": video}, timeout=120
            )
        log.info("[BG] ¡Video enviado!")

    except Exception as e:
        log.error(f"[BG] ERROR: {e}")
    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

# =============================================================================
# 7. ENDPOINTS
# =============================================================================
@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V20.0"}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho)
    return {"status": "ACCEPTED", "message": f"Video sobre '{request.tema}' en proceso."}
