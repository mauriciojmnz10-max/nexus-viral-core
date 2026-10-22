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

# URL de música de fondo libre de derechos (Ambient Cinematic)
MUSIC_URL = "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0c6ff1bab.mp3?filename=ambient-piano-amp-strings-10711.mp3"

app = FastAPI(title="Nexus V23.0 // Cinematic")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "misterio"

# =============================================================================
# 1. GENERACIÓN DE GUION (PROMPTS CINEMATOGRÁFICOS)
# =============================================================================
def generar_guion_estructurado(tema: str, nicho: str) -> list:
    log.info(f"[GROQ] Generando guion cinematográfico para: {tema}")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.1"
    }
    
    prompt = f"""
    Actúa como un director de cine y guionista experto en TikTok.
    Genera un guion de 5 escenas sobre: '{tema}', con un tono de {nicho}.
    
    REGLAS DE TEXTO:
    1. GANCHO: Frase que enganche en 3 segundos.
    2. DESARROLLO: 3 frases cortas y misteriosas.
    3. CIERRE: CTA magnético.
    4. Máximo 15 palabras por escena.

    REGLAS VISUALES (MUY IMPORTANTE):
    Para el campo "visual", escribe el prompt en INGLÉS para buscar el video en Pixabay.
    El prompt DEBE incluir términos cinematográficos como: "cinematic, 4k, dramatic lighting, slow motion, high quality, photorealistic".
    
    DEBES responder ÚNICAMENTE con un JSON válido:
    {{
      "escenas": [
        {{"texto": "Frase 1", "visual": "cinematic 4k shot of..."}},
        {{"texto": "Frase 2", "visual": "dramatic lighting, slow motion of..."}},
        {{"texto": "Frase 3", "visual": "photorealistic detail of..."}},
        {{"texto": "Frase 4", "visual": "epic cinematic background of..."}},
        {{"texto": "Frase 5", "visual": "high quality 4k shot of..."}}
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
# 2. VOZ (EDGE-TTS)
# =============================================================================
async def generar_audio_edge(texto: str, output_mp3: str):
    voice = "es-ES-AlvaroNeural" 
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(output_mp3)

def generar_audio_escena(texto: str, output_mp3: str) -> bool:
    log.info(f"[TTS] Generando audio para: {texto[:30]}...")
    try:
        asyncio.run(generar_audio_edge(texto, output_mp3))
        if os.path.getsize(output_mp3) > 1000: return True
    except Exception as e:
        log.warning(f"[TTS] Edge-TTS falló: {e}. Usando gTTS.")
        
    try:
        tts = gTTS(text=texto, lang='es', slow=False)
        tts.save(output_mp3)
        return True
    except Exception as e:
        log.error(f"[TTS] gTTS falló: {e}. Silencio.")
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
# 3. DESCARGA DE CLIPS (PIXABAY + MÚSICA)
# =============================================================================
def descargar_clip_vertical(query: str, output_file: str):
    if PIXABAY_API_KEY:
        try:
            url = "https://pixabay.com/api/videos/"
            # Buscamos calidad "medium" para equilibrar RAM y calidad visual
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
        except Exception as e:
            log.warning(f"[STOCK] Pixabay falló: {e}")
            
    log.warning("[STOCK] Generando fondo local.")
    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=720x1280:d=10,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", output_file]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception:
        return False

def descargar_musica(output_file: str):
    try:
        r = requests.get(MUSIC_URL, timeout=20)
        if r.status_code == 200:
            with open(output_file, "wb") as f:
                f.write(r.content)
            return True
    except Exception as e:
        log.warning(f"[MUSIC] Falló la descarga: {e}")
    return False

# =============================================================================
# 4. ENSAMBLAJE FINAL (CROSSFADE, MÚSICA Y SUBTÍTULOS)
# =============================================================================
def procesar_video_final(escenas: list, work_dir: str, output_final: str):
    try:
        # 1. Unir Audios
        log.info("[AUDIO] Uniendo voces...")
        combined_voz = AudioSegment.empty()
        for i in range(len(escenas)):
            audio_file = os.path.join(work_dir, f"audio_{i}.mp3")
            combined_voz += AudioSegment.from_file(audio_file, format="mp3")
        voz_maestra = os.path.join(work_dir, "voz_maestra.mp3")
        combined_voz.export(voz_maestra, format="mp3")

        # 2. Mezclar Música de Fondo
        log.info("[AUDIO] Mezclando música...")
        music_path = os.path.join(work_dir, "music.mp3")
        audio_maestro = os.path.join(work_dir, "audio_maestro.mp3")
        
        if descargar_musica(music_path):
            # Bajar volumen de música al 15% y recortar a la duración de la voz
            cmd_mix = [
                "ffmpeg", "-y", "-i", voz_maestra, "-stream_loop", "-1", "-i", music_path,
                "-filter_complex", "[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3[aout]",
                "-map", "[aout]", "-c:a", "libmp3lame", "-shortest", audio_maestro
            ]
            subprocess.run(cmd_mix, check=True, capture_output=True)
        else:
            shutil.copy(voz_maestra, audio_maestro)

        # 3. Generar SRT
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

        # 4. FFmpeg Ensamblaje Cinemático (Crossfade)
        log.info("[FFMPEG] Ensamblando video con transiciones...")
        inputs = []
        filter_complex = ""
        
        # Entradas de video
        for i in range(len(escenas)):
            video_path = os.path.join(work_dir, f"bg_{i}.mp4")
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            duracion = obtener_duracion_audio(audio_path)
            
            inputs.extend(["-i", video_path])
            # Escalar, cortar y preparar cada clip
            filter_complex += f"[{i}:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,setsar=1,trim=duration={duracion},setpts=PTS-STARTPTS[v{i}];"

        # Aplicar Crossfade (Transiciones suaves)
        # xfade necesita la duración exacta de cada clip y el offset (inicio de la transición)
        current_offset = 0.0
        last_output = "v0"
        
        for i in range(1, len(escenas)):
            audio_path = os.path.join(work_dir, f"audio_{i-1}.mp3")
            duracion_prev = obtener_duracion_audio(audio_path)
            current_offset += (duracion_prev - 0.5) # 0.5 seg de transición
            
            out_name = f"vx{i}"
            # xfade=transition=fade:duration=0.5:offset=X
            filter_complex += f"[{last_output}][v{i}]xfade=transition=fade:duration=0.5:offset={current_offset}[{out_name}];"
            last_output = out_name

        # Añadir subtítulos al último video
        style = "FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=200"
        filter_complex += f"[{last_output}]subtitles={srt_file}:force_style='{style}'[vout]"

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-i", audio_maestro,
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
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎬 *NEXUS V23.0* 🎬\n\n🎯 Tema: {tema}\n🎭 Nicho: {nicho}\n🎵 Música: ON\n✨ Transiciones: ON"}, 
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
    return {"status": "ONLINE", "engine": "Nexus V23.0"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, "Secretos del universo", "misterio")
    return {"status": "ACCEPTED", "message": "Video en proceso."}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho)
    return {"status": "ACCEPTED", "message": f"Video sobre '{request.tema}' en proceso."}
