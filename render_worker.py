import os
import json
import subprocess
import requests
import uuid
import asyncio
import edge_tts
from pydub import AudioSegment

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

def enviar_mensaje_telegram(texto):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def buscar_en_coverr(query, output):
    url = "https://api.coverr.co/videos"
    
    # Intento 1: Frase exacta (3 palabras)
    try:
        r = requests.get(url, params={"query": query, "per_page": 1, "orientation": "portrait"}, timeout=15)
        if r.status_code == 200 and r.json().get("hits"):
            video_url = r.json()["hits"][0].get("urls", {}).get("mp4_download") or r.json()["hits"][0].get("urls", {}).get("mp4")
            if video_url:
                with open(output, "wb") as f:
                    f.write(requests.get(video_url, timeout=30).content)
                print(f"[COVERR] Éxito con: {query}")
                return True
    except Exception as e:
        print(f"[COVERR] Error en intento 1: {e}")

    # Intento 2: Si falla, buscamos solo las primeras 2 palabras
    palabras = query.split()
    if len(palabras) > 2:
        query_corta = " ".join(palabras[:2])
        print(f"[COVERR] Reintentando con: {query_corta}")
        try:
            r = requests.get(url, params={"query": query_corta, "per_page": 1, "orientation": "portrait"}, timeout=15)
            if r.status_code == 200 and r.json().get("hits"):
                video_url = r.json()["hits"][0].get("urls", {}).get("mp4_download") or r.json()["hits"][0].get("urls", {}).get("mp4")
                if video_url:
                    with open(output, "wb") as f:
                        f.write(requests.get(video_url, timeout=30).content)
                    print(f"[COVERR] Éxito con: {query_corta}")
                    return True
        except Exception as e:
            print(f"[COVERR] Error en intento 2: {e}")

    return False

def descargar_clip_pixabay(query, output):
    """Respaldo por si Coverr falla."""
    try:
        url = "https://pixabay.com/api/videos/"
        params = {"key": PIXABAY_API_KEY, "q": query, "per_page": 3, "orientation": "vertical", "video_type": "film"}
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200 and r.json().get("hits"):
            video_url = r.json()["hits"][0].get("videos", {}).get("small", {}).get("url")
            if video_url:
                with open(output, "wb") as f:
                    f.write(requests.get(video_url, timeout=30).content)
                return True
    except: pass
    return False

async def gen_audio(texto, output):
    voice = "es-MX-JorgeNeural"
    try:
        communicate = edge_tts.Communicate(texto, voice)
        await communicate.save(output)
    except Exception as e:
        enviar_mensaje_telegram(f"❌ *Edge-TTS falló:* {str(e)}")
        raise Exception(f"Edge-TTS falló: {e}")

def main():
    work_dir = f"/tmp/nexus_{uuid.uuid4().hex}"
    os.makedirs(work_dir, exist_ok=True)

    scenes = json.loads(os.getenv("SCENES_JSON"))
    metadata = json.loads(os.getenv("METADATA_JSON"))

    try:
        audios = []
        for i, scene in enumerate(scenes):
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            asyncio.run(gen_audio(scene["texto"], audio_path))
            audios.append(audio_path)

        combined = AudioSegment.empty()
        for a in audios: combined += AudioSegment.from_file(a, format="mp3")
        audio_maestro = os.path.join(work_dir, "audio_maestro.mp3")
        combined.export(audio_maestro, format="mp3")

        videos = []
        for i, scene in enumerate(scenes):
            v_path = os.path.join(work_dir, f"bg_{i}.mp4")
            # 1. Coverr (Principal)
            exito = buscar_en_coverr(scene["visual"], v_path)
            if not exito:
                # 2. Pixabay (Respaldo)
                print(f"[BG] Coverr falló para escena {i+1}. Usando Pixabay...")
                exito = descargar_clip_pixabay(scene["visual"], v_path)
                if not exito:
                    # 3. Fondo de gradiente
                    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", v_path], check=True, capture_output=True)
            videos.append(v_path)

        srt_path = os.path.join(work_dir, "subs.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            t = 0.0
            for i, scene in enumerate(scenes):
                dur = len(AudioSegment.from_file(audios[i], format="mp3")) / 1000.0
                f.write(f"{i+1}\n00:00:{int(t):02},{int((t%1)*1000):03} --> 00:00:{int(t+dur):02},{int(((t+dur)%1)*1000):03}\n{scene['texto']}\n\n")
                t += dur

        inputs = []
        filter_str = ""
        for i in range(len(scenes)):
            inputs.extend(["-i", videos[i]])
            dur = len(AudioSegment.from_file(audios[i], format="mp3")) / 1000.0
            # Filtro de color cinematográfico y escala
            filter_str += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,eq=contrast=1.2:saturation=1.3,trim=duration={dur},setpts=PTS-STARTPTS[v{i}];"

        concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
        filter_str += f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0[v];"
        style = "FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=150"
        filter_str += f"[v]subtitles={srt_path}:force_style='{style}'[vout]"

        final_path = os.path.join(work_dir, "final.mp4")
        cmd = ["ffmpeg", "-y", *inputs, "-i", audio_maestro, "-filter_complex", filter_str, "-map", "[vout]", "-map", f"{len(scenes)}:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", final_path]
        subprocess.run(cmd, check=True, capture_output=True)

        caption = f"🎬 *NEXUS RENDER (Coverr Pro)* 🎬\n\n🎯 *PLATAFORMA:* {metadata['plataforma']}\n📌 *TÍTULO:* {metadata['titulo']}\n\n📝 *DESCRIPCIÓN:*\n{metadata['descripcion']}\n\n🏷️ *HASHTAGS:*\n{metadata['hashtags']}\n\n🔗 *CTA:*\n{metadata['cta_link']}"
        
        with open(final_path, "rb") as video:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": video}, timeout=120)

    except Exception as e:
        enviar_mensaje_telegram(f"❌ *Error crítico en el renderizado:* {str(e)}")

if __name__ == "__main__":
    main()
