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

app = FastAPI(title="Nexus V22.0 // Ultra Light")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "misterio"

# =============================================================================
# 1. GENERACIÓN DE GUION (4 ESCENAS)
# =============================================================================
def generar_guion_estructurado(tema: str, nicho: str) -> list:
    log.info(f"[GROQ] Generando guion de 4 escenas para: {tema}")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.1"
    }
    
    prompt = f"""
    Actúa como un guionista experto en videos virales de TikTok.
    Genera un guion de 4 escenas sobre: '{tema}', con un tono de {nicho}.
    
    REGLAS:
    1. GANCHO: La primera frase debe enganchar en 3 segundos.
    2. DESARROLLO: 2 frases que cuenten una historia o datos curiosos.
    3. CIERRE: Una frase final con llamado a la acción (CTA).
    4. Cada escena debe tener entre 12 y 18 palabras.
    
    DEBES responder ÚNICAMENTE con un JSON válido, sin markdown, con esta estructura exacta:
    {{
      "escenas": [
        {{"texto": "Gancho (máx 15 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Desarrollo 1 (máx 18 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "Desarrollo 2 (máx 18 palabras)", "visual": "english prompt for stock video"}},
        {{"texto": "CTA (máx 15 palabras)", "visual": "english prompt for stock video"}}
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

def generar_audio_escena(texto: str, output_mp3: str) -> bool:
    log.info(f"[TTS] Generando audio para: {texto[:30]}...")
    
    try:
        asyncio.run(generar_audio_edge(texto, output_mp3))
        if os.path.getsize(output_mp3) > 1000:
            return True
    except Exception as e:
        log.warning(f"[TTS] Edge-TTS falló: {e}. Usando gTTS.")
        
    try:
        tts = gTTS(text=texto, lang='es', slow=False)
        tts.save(output_mp3)
        return True
    except Exception as e:
        log.error(f"[TTS] gTTS también falló: {e}. Silencio.")
        try:
            silence = AudioSegment.silent(duration=3000)
            silence.export(output_mp3, format="mp3")
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
                    video_url = videos.get("small", {}).get("url") or videos.get("medium", {}).get("url")
                    if video_url:
                        with open(output_file, "wb") as f:
                            f.write(requests.get(video_url, timeout=30).content)
                        return True
        except Exception:
            pass
    # Fallback
    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=720x1280:d=10,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", output_file]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception:
        return False

# =============================================================================
# 4. CONCATENACIÓN EN UN SOLO COMANDO (BAJO CONSUMO DE RAM)
# =============================================================================
def procesar_video_final(escenas: list, work_dir: str, output_final: str):
    try:
        # 1. Unir todos los audios en un MP3 maestro con pydub
        log.info("[AUDIO] Uniendo audios en MP3 maestro...")
        combined = AudioSegment.empty()
        for i in range(len(escenas)):
            audio_file = os.path.join(work_dir, f"audio_{i}.mp3")
            segment = AudioSegment.from_file(audio_file, format="mp3")
            combined += segment
        audio_maestro = os.path.join(work_dir, "audio_maestro.mp3")
        combined.export(audio_maestro, format="mp3")

        # 2. Generar el SRT
        log.info("[SRT] Generando subtítulos...")
        srt_file = os.path.join(work_dir, "subs.srt")
        current_time = 0.0
        with open(srt_file, "w", encoding="utf-8") as f:
            for i, escena in enumerate(escenas):
                audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
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

        # 3. Comando único de FFmpeg con filtro complejo
        log.info("[FFMPEG] Ensamblando video final en un solo paso...")
        
        # Construir la entrada de argumentos para FFmpeg
        inputs = []
        filter_complex = ""
        
        for i in range(len(escenas)):
            video_path = os.path.join(work_dir, f"bg_{i}.mp4")
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            duracion = obtener_duracion_audio(audio_path)
            
            inputs.extend(["-i", video_path])
            # Escalar cada video y cortarlo a la duración del audio
            filter_complex += f"[{i}:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,setsar=1,trim=duration={duracion},setpts=PTS-STARTPTS[v{i}];"

        # Concatenar todos los videos procesados
        concat_inputs = "".join([f"[v{i}]" for i in range(len(escenas))])
        filter_complex += f"{concat_inputs}concat=n={len(escenas)}:v=1:a=0[v];"
        
        # Añadir subtítulos
        style = "FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=200"
        filter_complex += f"[v]subtitles={srt_file}:force_style='{style}'[vout]"

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-i", audio_maestro,  # El audio maestro va al final
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", f"{len(escenas)}:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
            "-c:a", "aac", "-shortest",
            output_final
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"[FFMPEG] Error: {e.stderr.decode()[:500]}")
        return False
    except Exception as e:
        log.error(f"[FFMPEG] Error inesperado: {e}")
        return False

# =============================================================================
# 5. LÓGICA DE FONDO
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

        for i, escena in enumerate(escenas):
            log.info(f"[BG] Preparando Escena {i+1}/{len(escenas)}...")
            
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            video_bg = os.path.join(work_dir, f"bg_{i}.mp4")

            generar_audio_escena(escena["texto"], audio_path)
            
            if not descargar_clip_vertical(escena.get("visual", "abstract"), video_bg):
                log.error(f"[BG] Fallo stock escena {i+1}")
                return

        log.info("[BG] Ensamblando video final...")
        video_final = os.path.join(work_dir, "final.mp4")
        if not procesar_video_final(escenas, work_dir, video_final):
            log.error("[BG] Fallo en el ensamblaje final.")
            return

        log.info("[BG] Enviando a Telegram...")
        with open(video_final, "rb") as video:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", 
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎬 *NEXUS V22.0* 🎬\n\n🎯 Tema: {tema}\n🎭 Nicho: {nicho}"}, 
                files={"video": video}, timeout=120
            )
        log.info("[BG] ¡Video enviado!")

    except Exception as e:
        log.error(f"[BG] ERROR: {e}")
    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

# =============================================================================
# 6. ENDPOINTS
# =============================================================================
@app.get("/")
async def root():
    return {"status": "ONLINE", "engine": "Nexus V22.0"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, "Secretos del universo", "misterio")
    return {"status": "ACCEPTED", "message": "Video en proceso con tema por defecto."}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho)
    return {"status": "ACCEPTED", "message": f"Video sobre '{request.tema}' en proceso."}
