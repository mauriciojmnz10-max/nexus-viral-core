import os
import json
import subprocess
import requests
import uuid
import asyncio
import edge_tts
from pydub import AudioSegment

# Configuración
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

def descargar_clip(query, output):
    # 1. Buscar en Pixabay
    try:
        url = "https://pixabay.com/api/videos/"
        params = {
            "key": PIXABAY_API_KEY, 
            "q": query, 
            "per_page": 5, 
            "orientation": "vertical", 
            "video_type": "film"
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                for hit in hits:
                    video_url = hit.get("videos", {}).get("medium", {}).get("url") or hit.get("videos", {}).get("small", {}).get("url")
                    if video_url:
                        print(f"Descargando de Pixabay: {query}")
                        with open(output, "wb") as f:
                            f.write(requests.get(video_url, timeout=30).content)
                        return True
    except Exception as e:
        print(f"Error en Pixabay: {e}")

    # 2. Fallback: Degradado elegante
    print(f"Fallo Pixabay para '{query}'. Generando fondo degradado...")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", 
            "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", output
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Error generando fondo: {e}")
        return False

async def gen_audio(texto, output):
    voice = "es-MX-JorgeNeural"
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(output)

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

    # 3. Descargar Videos
    videos = []
    for i, scene in enumerate(scenes):
        v_path = os.path.join(work_dir, f"bg_{i}.mp4")
        descargar_clip(scene["visual"], v_path)
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
    caption = f"🎬 *NEXUS RENDER (GitHub)* 🎬\n\n🎯 *PLATAFORMA:* {metadata['plataforma']}\n📌 *TÍTULO:* {metadata['titulo']}\n\n📝 *DESCRIPCIÓN:*\n{metadata['descripcion']}\n\n🏷️ *HASHTAGS:*\n{metadata['hashtags']}\n\n🔗 *CTA:*\n{metadata['cta_link']}"
    
    with open(final_path, "rb") as video:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": video}, timeout=120)

if __name__ == "__main__":
    main()
