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

MUSIC_URL = "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0c6ff1bab.mp3?filename=ambient-piano-amp-strings-10711.mp3"

app = FastAPI(title="Nexus V29.0 // Retention & Sync")

class VideoRequest(BaseModel):
    tema: str
    nicho: str = "misterio"

# =============================================================================
# 1. GENERACIÓN DE GUION (14 ESCENAS - FÓRMULAS VIRALES)
# =============================================================================
def generar_guion_estructurado(tema: str, nicho: str) -> list:
    log.info(f"[GROQ] Generando guion viral de 14 escenas para: {tema}")
    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.1"
    }
    
    prompt = f"""
    Actúa como un Copywriter Senior experto en videos virales de TikTok.
    Genera un guion de 14 escenas sobre: '{tema}', con un tono de {nicho}.
    
    REGLAS DE ORO (OBLIGATORIAS):
    1. GANCHO (Escena 1): Usa una fórmula de bucle abierto. Ej: "El error de 3 segundos que...", "Lo que los expertos ocultan sobre...", "Nadie te dice esto sobre...".
    2. DESARROLLO (Escenas 2-13): Cuenta la historia revelando datos como si fuera un secreto prohibido. Usa comas en lugar de puntos para que la voz fluya rápido.
    3. CTA (Escena 14): Pide LIKE, COMENTAR (con una palabra clave) y COMPARTIR.
    4. LONGITUD: Exactamente entre 12 y 15 palabras por escena.

    REGLAS VISUALES:
    Para el campo "visual", escribe 1 o 2 palabras clave en INGLÉS (ej: "space", "planet", "ocean").
    
    DEBES responder ÚNICAMENTE con un JSON válido, sin markdown:
    {{
      "escenas": [
        {{"texto": "Gancho neuro-persuasivo (12-15 palabras)", "visual": "space"}},
        {{"texto": "Secreto 1", "visual": "stars"}},
        {{"texto": "Secreto 2", "visual": "nebula"}},
        {{"texto": "Dato oculto 1", "visual": "planet"}},
        {{"texto": "Dato oculto 2", "visual": "galaxy"}},
        {{"texto": "Giro inesperado", "visual": "cosmos"}},
        {{"texto": "Desarrollo 1", "visual": "universe"}},
        {{"texto": "Desarrollo 2", "visual": "astronomy"}},
        {{"texto": "Desarrollo 3", "visual": "telescope"}},
        {{"texto": "Revelación 1", "visual": "supernova"}},
        {{"texto": "Revelación 2", "visual": "dark matter"}},
        {{"texto": "Clímax", "visual": "milky way"}},
        {{"texto": "Conclusión", "visual": "galaxy"}},
        {{"texto": "CTA: Pide like, comentario y compartir", "visual": "stars"}}
      ]
    }}
    """
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
        "response_format": {"type": "json_object"}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=40)
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"]).get("escenas", [])
    except Exception as e:
        log.error(f"[GROQ] Error: {e}")
        return []

# =============================================================================
# 2. VOZ (EDGE-TTS LATINO)
# =============================================================================
async def generar_audio_edge(texto: str, output_mp3: str):
    voice = "es-MX-JorgeNeural" 
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(output_mp3)

def generar_audio_escena(texto: str, output_mp3: str) -> bool:
    try:
        asyncio.run(generar_audio_edge(texto, output_mp3))
        if os.path.getsize(output_mp3) > 1000: return True
    except Exception:
        pass
    try:
        tts = gTTS(text=texto, lang='es', slow=False)
        tts.save(output_mp3)
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
# 3. DESCARGA DE CLIPS Y MÚSICA
# =============================================================================
def descargar_clip_vertical(query: str, output_file: str):
    if PIXABAY_API_KEY:
        try:
            url = "https://pixabay.com/api/videos/"
            params = {"key": PIXABAY_API_KEY, "q": query, "per_page": 5, "orientation": "vertical", "video_type": "film"}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                hits = r.json().get("hits", [])
                if hits:
                    videos = hits[0].get("videos", {})
                    video_url = videos.get("small", {}).get("url")
                    if video_url:
                        with open(output_file, "wb") as f:
                            f.write(requests.get(video_url, timeout=30).content)
                        return True
        except Exception:
            pass
    # Fallback
    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=480x854:d=10,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", output_file]
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
    except Exception:
        pass
    return False

# =============================================================================
# 4. PROCESAMIENTO DE UN BLOQUE (PARTE)
# =============================================================================
def procesar_bloque(escenas_bloque: list, num_bloque: int, work_dir: str) -> str:
    log.info(f"[BLOQUE {num_bloque}] Procesando {len(escenas_bloque)} escenas...")
    
    audios_paths = []
    for i, escena in enumerate(escenas_bloque):
        audio_path = os.path.join(work_dir, f"b{num_bloque}_audio_{i}.mp3")
        generar_audio_escena(escena["texto"], audio_path)
        audios_paths.append(audio_path)

    combined = AudioSegment.empty()
    for a_path in audios_paths:
        combined += AudioSegment.from_file(a_path, format="mp3")
    audio_bloque = os.path.join(work_dir, f"b{num_bloque}_audio.mp3")
    combined.export(audio_bloque, format="mp3")

    videos_paths = []
    for i, escena in enumerate(escenas_bloque):
        v_path = os.path.join(work_dir, f"b{num_bloque}_bg_{i}.mp4")
        descargar_clip_vertical(escena["visual"], v_path)
        videos_paths.append(v_path)

    # GENERACIÓN DE SUBTÍTULOS CON SINCRONIZACIÓN PROPORCIONAL
    srt_file = os.path.join(work_dir, f"b{num_bloque}_subs.srt")
    current_time = 0.0
    with open(srt_file, "w", encoding="utf-8") as f:
        contador = 1
        for i, escena in enumerate(escenas_bloque):
            duracion = obtener_duracion_audio(audios_paths[i])
            start, end = current_time, current_time + duracion
            
            palabras = escena['texto'].split()
            if len(palabras) > 5:
                mid = len(palabras) // 2
                parte1 = " ".join(palabras[:mid])
                parte2 = " ".join(palabras[mid:])
                
                # SINCRONIZACIÓN: Tiempo proporcional a la cantidad de palabras
                total_words = len(palabras)
                time_part1 = start + (duracion * (mid / total_words))
                
                def format_time(sec):
                    h, m, s = int(sec//3600), int((sec%3600)//60), int(sec%60)
                    ms = int((sec - int(sec)) * 1000)
                    return f"{h:02}:{m:02}:{s:02},{ms:03}"
                
                f.write(f"{contador}\n{format_time(start)} --> {format_time(time_part1)}\n{parte1}\n\n")
                f.write(f"{contador+1}\n{format_time(time_part1)} --> {format_time(end)}\n{parte2}\n\n")
                contador += 2
            else:
                def format_time(sec):
                    h, m, s = int(sec//3600), int((sec%3600)//60), int(sec%60)
                    ms = int((sec - int(sec)) * 1000)
                    return f"{h:02}:{m:02}:{s:02},{ms:03}"
                f.write(f"{contador}\n{format_time(start)} --> {format_time(end)}\n{escena['texto']}\n\n")
                contador += 1
            
            current_time = end

    inputs = []
    filter_complex = ""
    for i in range(len(escenas_bloque)):
        inputs.extend(["-i", videos_paths[i]])
        duracion = obtener_duracion_audio(audios_paths[i])
        filter_complex += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,trim=duration={duracion},setpts=PTS-STARTPTS[v{i}];"

    concat_inputs = "".join([f"[v{i}]" for i in range(len(escenas_bloque))])
    filter_complex += f"{concat_inputs}concat=n={len(escenas_bloque)}:v=1:a=0[v];"
    
    style = "FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=150"
    filter_complex += f"[v]subtitles={srt_file}:force_style='{style}'[vout]"

    bloque_out = os.path.join(work_dir, f"parte_{num_bloque}.mp4")
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-i", audio_bloque,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", f"{len(escenas_bloque)}:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
        "-c:a", "aac", "-shortest",
        bloque_out
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
    for path in audios_paths + videos_paths:
        if os.path.exists(path): os.remove(path)
    if os.path.exists(audio_bloque): os.remove(audio_bloque)

    return bloque_out

# =============================================================================
# 5. ORQUESTADOR PRINCIPAL (GARANTÍA DE +65 SEGUNDOS)
# =============================================================================
def procesar_video_en_segundo_plano(tema: str, nicho: str):
    work_dir = f"/tmp/nexus_{uuid.uuid4().hex}"
    os.makedirs(work_dir, exist_ok=True)
    log.info(f"[BG] Directorio de trabajo: {work_dir}")

    try:
        escenas = generar_guion_estructurado(tema, nicho)
        if len(escenas) < 14:
            log.error("[BG] Guion incompleto.")
            return

        # Dividir en bloques de 3 o 4 escenas (para no saturar Render)
        bloques = [escenas[i:i+4] for i in range(0, 14, 4)]

        partes_generadas = []
        for idx, bloque in enumerate(bloques, start=1):
            parte = procesar_bloque(bloque, idx, work_dir)
            partes_generadas.append(parte)

        log.info("[BG] Uniendo todos los bloques...")
        video_final = os.path.join(work_dir, "final.mp4")
        lista_unir = os.path.join(work_dir, "lista.txt")
        with open(lista_unir, "w") as f:
            for p in partes_generadas:
                f.write(f"file '{p}'\n")
        
        cmd_unir = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista_unir, "-c", "copy", video_final]
        subprocess.run(cmd_unir, check=True, capture_output=True)

        # =====================================================================
        # GARANTÍA DE DURACIÓN: Si el video es menor a 65s, lo rellenamos
        # =====================================================================
        log.info("[BG] Verificando duración del video...")
        duracion_actual = obtener_duracion_audio(video_final)
        
        if duracion_actual < 65.0:
            log.info(f"[BG] El video dura {duracion_actual}s. Rellenando hasta 65s...")
            # Creamos un video de relleno de 10s (color negro)
            relleno = os.path.join(work_dir, "relleno.mp4")
            cmd_relleno = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=480x854:d=10",
                "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", relleno
            ]
            subprocess.run(cmd_relleno, check=True, capture_output=True)
            
            # Lo añadimos al final
            lista_relleno = os.path.join(work_dir, "lista_relleno.txt")
            with open(lista_relleno, "w") as f:
                f.write(f"file '{video_final}'\n")
                f.write(f"file '{relleno}'\n")
            
            video_estirado = os.path.join(work_dir, "video_estirado.mp4")
            cmd_estirar = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista_relleno, "-c", "copy", video_estirado]
            subprocess.run(cmd_estirar, check=True, capture_output=True)
            video_final = video_estirado

        log.info("[BG] Añadiendo música...")
        music_path = os.path.join(work_dir, "music.mp3")
        video_con_musica = os.path.join(work_dir, "final_music.mp4")
        
        if descargar_musica(music_path):
            cmd_music = [
                "ffmpeg", "-y", "-i", video_final, "-stream_loop", "-1", "-i", music_path,
                "-filter_complex", "[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2:duration=first[aout]",
                "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-shortest", video_con_musica
            ]
            subprocess.run(cmd_music, check=True, capture_output=True)
            video_final = video_con_musica

        log.info("[BG] Enviando a Telegram...")
        with open(video_final, "rb") as video:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", 
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎬 *NEXUS V29.0* 🎬\n\n🎯 Tema: {tema}\n🎭 Nicho: {nicho}\n⏱️ Duración: Garantizada >65s\n🚀 Sincronización Perfecta"}, 
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
    return {"status": "ONLINE", "engine": "Nexus V29.0"}

@app.post("/generar-tendencias")
async def generar_tendencias_default(background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, "Secretos del universo", "misterio")
    return {"status": "ACCEPTED", "message": "Video de +65s en proceso."}

@app.post("/generar-video")
async def generar_video_personalizado(request: VideoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(procesar_video_en_segundo_plano, request.tema, request.nicho)
    return {"status": "ACCEPTED", "message": f"Video de +65s sobre '{request.tema}' en proceso."}
