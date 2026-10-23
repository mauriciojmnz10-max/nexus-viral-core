import os
import json
import subprocess
import requests
import uuid
import asyncio
import time
import edge_tts
from pydub import AudioSegment

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
AGNES_API_KEY = os.getenv("AGNES_API_KEY") # Nueva variable

AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"

def generar_video_ia(prompt, output_file):
    """Genera un video de 5s con Agnes AI basado en el prompt."""
    print(f"[AGNES] Generando video para: {prompt[:50]}...")
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "agnes-video-2.5-flash",
        "prompt": prompt,
        "seconds": "5",
        "mode": "text",
        "size": "720P",
        "aspect_ratio": "9:16" # Formato vertical para TikTok/Shorts
    }
    
    try:
        # 1. Crear la tarea de generación
        r = requests.post(f"{AGNES_BASE_URL}/videos", headers=headers, json=payload, timeout=30)
        if r.status_code != 200:
            print(f"[AGNES] Error al crear tarea: {r.status_code} - {r.text}")
            return False
        
        data = r.json()
        video_id = data.get("video_id")
        if not video_id:
            print("[AGNES] No se recibió video_id.")
            return False
            
        print(f"[AGNES] Tarea creada: {video_id}. Esperando generación...")
        
        # 2. Polling para esperar a que termine
        max_intentos = 60 # 60 * 5s = 5 minutos máximo
        for i in range(max_intentos):
            time.sleep(5)
            poll_url = f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}&model_name=agnes-video-2.5-flash"
            poll_r = requests.get(poll_url, headers={"Authorization": f"Bearer {AGNES_API_KEY}"}, timeout=15)
            
            if poll_r.status_code == 200:
                status_data = poll_r.json()
                status = status_data.get("status")
                progress = status_data.get("progress", 0)
                print(f"[AGNES] Intento {i+1}: {status} ({progress}%)")
                
                if status == "completed":
                    video_url = status_data.get("url")
                    if video_url:
                        print(f"[AGNES] Video listo. Descargando...")
                        with open(output_file, "wb") as f:
                            f.write(requests.get(video_url, timeout=30).content)
                        return True
                    else:
                        print("[AGNES] Completado pero sin URL.")
                        return False
                elif status == "failed":
                    print(f"[AGNES] Falló: {status_data.get('error')}")
                    return False
            else:
                print(f"[AGNES] Error en polling: {poll_r.status_code}")
        
        print("[AGNES] Timeout esperando el video.")
        return False
        
    except Exception as e:
        print(f"[AGNES] Excepción: {e}")
        return False

def descargar_clip_pixabay(query, output):
    """Plan B: Buscar en Pixabay si Agnes falla."""
    print(f"[PIXABAY] Fallback para: {query}")
    try:
        url = "https://pixabay.com/api/videos/"
        params = {"key": PIXABAY_API_KEY, "q": query, "per_page": 3, "orientation": "vertical", "video_type": "film"}
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                video_url = hits[0].get("videos", {}).get("small", {}).get("url")
                if video_url:
                    with open(output, "wb") as f:
                        f.write(requests.get(video_url, timeout=30).content)
                    return True
    except Exception as e:
        print(f"[PIXABAY] Error: {e}")
    return False

async def gen_audio(texto, output):
    voice = "es-MX-JorgeNeural"
    try:
        communicate = edge_tts.Communicate(texto, voice)
        await communicate.save(output)
        print(f"Edge-TTS OK para: {texto[:20]}...")
    except Exception as e:
        print(f"❌ Edge-TTS falló: {e}. Usando gTTS como respaldo.")
        from gtts import gTTS
        tts = gTTS(text=texto, lang='es', slow=False)
        tts.save(output)

def main():
    work_dir = f"/tmp/nexus_{uuid.uuid4().hex}"
    os.makedirs(work_dir, exist_ok=True)

    scenes = json.loads(os.getenv("SCENES_JSON"))
    metadata = json.loads(os.getenv("METADATA_JSON"))

    # 1. Generar Audios
    audios = []
    for i, scene in enumerate(scenes):
        audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
        asyncio.run(gen_audio(scene["texto"], audio_path))
        audios.append(audio_path)

    # 2. Unir Audios
    combined = AudioSegment.empty()
    for a in audios: combined += AudioSegment.from_file(a, format="mp3")
    audio_maestro = os.path.join(work_dir, "audio_maestro.mp3")
    combined.export(audio_maestro, format="mp3")

    # 3. Generar/Descargar Videos de Fondo
    videos = []
    for i, scene in enumerate(scenes):
        v_path = os.path.join(work_dir, f"bg_{i}.mp4")
        # Intentar con Agnes AI primero
        exito = generar_video_ia(scene["visual"], v_path)
        if not exito:
            # Si Agnes falla, usar Pixabay
            print(f"[BG] Agnes falló para escena {i+1}. Usando Pixabay...")
            exito = descargar_clip_pixabay(scene["visual"], v_path)
            if not exito:
                # Si Pixabay también falla, generar un fondo de degradado
                print(f"[BG] Pixabay también falló. Generando fondo de respaldo...")
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", v_path], check=True, capture_output=True)
        videos.append(v_path)

    # 4. Generar SRT
    srt_path = os.path.join(work_dir, "subs.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        t = 0.0
        for i, scene in enumerate(scenes):
            dur = len(AudioSegment.from_file(audios[i], format="mp3")) / 1000.0
            f.write(f"{i+1}\n00:00:{int(t):02},{int((t%1)*1000):03} --> 00:00:{int(t+dur):02},{int(((t+dur)%1)*1000):03}\n{scene['texto']}\n\n")
            t += dur

    # 5. Ensamblar Video
    inputs = []
    filter_str = ""
    for i in range(len(scenes)):
        inputs.extend(["-i", videos[i]])
        dur = len(AudioSegment.from_file(audios[i], format="mp3")) / 1000.0
        filter_str += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,trim=duration={dur},setpts=PTS-STARTPTS[v{i}];"

    concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
    filter_str += f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0[v];"
    style = "FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=150"
    filter_str += f"[v]subtitles={srt_path}:force_style='{style}'[vout]"

    final_path = os.path.join(work_dir, "final.mp4")
    cmd = ["ffmpeg", "-y", *inputs, "-i", audio_maestro, "-filter_complex", filter_str, "-map", "[vout]", "-map", f"{len(scenes)}:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", final_path]
    subprocess.run(cmd, check=True, capture_output=True)

    # 6. Enviar a Telegram
    caption = f"🎬 *NEXUS RENDER (IA)* 🎬\n\n🎯 *PLATAFORMA:* {metadata['plataforma']}\n📌 *TÍTULO:* {metadata['titulo']}\n\n📝 *DESCRIPCIÓN:*\n{metadata['descripcion']}\n\n🏷️ *HASHTAGS:*\n{metadata['hashtags']}\n\n🔗 *CTA:*\n{metadata['cta_link']}"
    
    with open(final_path, "rb") as video:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": video}, timeout=120)

if __name__ == "__main__":
    main()
