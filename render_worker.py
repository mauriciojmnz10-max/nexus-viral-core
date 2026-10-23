import os
import json
import subprocess
import requests
import uuid
import asyncio
import edge_tts
from pydub import AudioSegment
import urllib.parse

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

def enviar_mensaje_telegram(texto):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}, timeout=10)
    except: pass

# --- FUENTE 1: PIXABAY (Imágenes y Videos) ---
def buscar_pixabay(query, output_dir, es_video=False):
    try:
        url = "https://pixabay.com/api/videos/" if es_video else "https://pixabay.com/api/"
        params = {"key": PIXABAY_API_KEY, "q": query, "per_page": 3, "orientation": "vertical", "safesearch": "true"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                if es_video:
                    video_url = hits[0].get("videos", {}).get("small", {}).get("url")
                    if video_url:
                        out_path = os.path.join(output_dir, f"pixabay_{uuid.uuid4().hex}.mp4")
                        with open(out_path, "wb") as f:
                            f.write(requests.get(video_url, timeout=15).content)
                        return out_path, True
                else:
                    img_url = hits[0].get("largeImageURL")
                    if img_url:
                        out_path = os.path.join(output_dir, f"pixabay_{uuid.uuid4().hex}.jpg")
                        with open(out_path, "wb") as f:
                            f.write(requests.get(img_url, timeout=15).content)
                        return out_path, False
    except: pass
    return None, None

# --- FUENTE 2: WIKIPEDIA (Respaldo) ---
def buscar_wikipedia(query, output_dir):
    try:
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(query)}&prop=pageimages&format=json&pithumbsize=1000"
        r = requests.get(search_url, timeout=10).json()
        pages = r.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if "thumbnail" in page_data:
                img_url = page_data["thumbnail"]["source"]
                out_path = os.path.join(output_dir, f"wiki_{uuid.uuid4().hex}.jpg")
                with open(out_path, "wb") as f:
                    f.write(requests.get(img_url, timeout=15).content)
                return out_path, False
    except: pass
    return None, None

# --- FUENTE 3: COVERR (Video de respaldo) ---
def buscar_coverr(query, output_dir):
    try:
        url = "https://api.coverr.co/videos"
        r = requests.get(url, params={"query": query, "per_page": 1, "orientation": "portrait"}, timeout=5)
        if r.status_code == 200 and r.json().get("hits"):
            video_url = r.json()["hits"][0].get("urls", {}).get("mp4_download") or r.json()["hits"][0].get("urls", {}).get("mp4")
            if video_url:
                out_path = os.path.join(output_dir, f"coverr_{uuid.uuid4().hex}.mp4")
                with open(out_path, "wb") as f:
                    f.write(requests.get(video_url, timeout=15).content)
                return out_path, True
    except: pass
    return None, None

def procesar_imagen_a_video(img_path, output_video, duracion):
    try:
        temp_mp4 = output_video.replace(".mp4", "_temp.mp4")
        cmd_convert = ["ffmpeg", "-y", "-loop", "1", "-i", img_path, "-t", "1", "-vf", "scale=800:1422,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", temp_mp4]
        subprocess.run(cmd_convert, check=True, capture_output=True)
        
        frames = int(duracion * 30)
        cmd_zoom = ["ffmpeg", "-y", "-i", temp_mp4, "-vf", f"zoompan=z='min(zoom+0.0015,1.5)':d={frames}:s=480x854", "-t", str(duracion), "-c:v", "libx264", "-preset", "ultrafast", output_video]
        subprocess.run(cmd_zoom, check=True, capture_output=True)
        
        if os.path.exists(temp_mp4): os.remove(temp_mp4)
        return True
    except Exception as e:
        print(f"[ERROR IMAGEN] {e}")
        return False

async def gen_audio(texto, output):
    voice = "es-ES-ElviraNeural" 
    try:
        communicate = edge_tts.Communicate(texto, voice, rate="+10%")
        await asyncio.wait_for(communicate.save(output), timeout=15)
    except Exception as e:
        raise Exception(f"Edge-TTS falló: {e}")

def main():
    work_dir = f"/tmp/nexus_{uuid.uuid4().hex}"
    os.makedirs(work_dir, exist_ok=True)

    scenes = json.loads(os.getenv("SCENES_JSON"))
    metadata = json.loads(os.getenv("METADATA_JSON"))

    try:
        audios = []
        duraciones = []
        for i, scene in enumerate(scenes):
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            asyncio.run(gen_audio(scene["texto"], audio_path))
            audios.append(audio_path)
            duraciones.append(len(AudioSegment.from_file(audio_path, format="mp3")) / 1000.0)

        combined = AudioSegment.empty()
        for a in audios: combined += AudioSegment.from_file(a, format="mp3")
        audio_maestro = os.path.join(work_dir, "audio_maestro.mp3")
        combined.export(audio_maestro, format="mp3")

        clips = []
        for i, scene in enumerate(scenes):
            final_bg = os.path.join(work_dir, f"bg_{i}.mp4")
            dur = duraciones[i]
            query = scene["visual"]
            print(f"[ESCENA {i+1}] Buscando: {query}")
            
            # 1. Pixabay (Imagen)
            path, is_video = buscar_pixabay(query, work_dir, es_video=False)
            if path:
                print(f"  -> Pixabay Imagen: {path}")
                procesar_imagen_a_video(path, final_bg, dur)
                clips.append(final_bg)
                continue

            # 2. Pixabay (Video)
            path, is_video = buscar_pixabay(query, work_dir, es_video=True)
            if path:
                print(f"  -> Pixabay Video: {path}")
                os.rename(path, final_bg)
                clips.append(final_bg)
                continue

            # 3. Wikipedia (Imagen)
            path, is_video = buscar_wikipedia(query, work_dir)
            if path:
                print(f"  -> Wikipedia Imagen: {path}")
                procesar_imagen_a_video(path, final_bg, dur)
                clips.append(final_bg)
                continue

            # 4. Coverr (Video)
            path, is_video = buscar_coverr(query, work_dir)
            if path:
                print(f"  -> Coverr Video: {path}")
                os.rename(path, final_bg)
                clips.append(final_bg)
                continue

            # 5. Gradiente (Último recurso)
            print(f"  -> Gradiente para escena {i+1}")
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", final_bg], check=True, capture_output=True)
            clips.append(final_bg)

        # Generar SRT
        srt_path = os.path.join(work_dir, "subs.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            t = 0.0
            for i, scene in enumerate(scenes):
                dur = duraciones[i]
                palabras = scene['texto'].split()
                bloques = [" ".join(palabras[j:j+3]) for j in range(0, len(palabras), 3)]
                tiempo_por_bloque = dur / len(bloques) if bloques else dur
                
                for k, bloque in enumerate(bloques):
                    start = t + (k * tiempo_por_bloque)
                    end = start + tiempo_por_bloque
                    f.write(f"{i}_{k}\n00:00:{int(start):02},{int((start%1)*1000):03} --> 00:00:{int(end):02},{int(((end)%1)*1000):03}\n{bloque}\n\n")
                t += dur

        inputs = []
        filter_str = ""
        for i in range(len(scenes)):
            inputs.extend(["-i", clips[i]])
            dur = duraciones[i]
            filter_str += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,trim=duration={dur},setpts=PTS-STARTPTS[v{i}];"

        concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
        filter_str += f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0[v];"
        
        style = "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=150,Bold=1"
        filter_str += f"[v]subtitles={srt_path}:force_style='{style}'[vout]"

        final_path = os.path.join(work_dir, "final.mp4")
        cmd = ["ffmpeg", "-y", *inputs, "-i", audio_maestro, "-filter_complex", filter_str, "-map", "[vout]", "-map", f"{len(scenes)}:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", final_path]
        subprocess.run(cmd, check=True, capture_output=True)

        nicho_usado = metadata.get("nicho_usado", "No especificado")
        caption = f"🎬 *NEXUS RENDER (Híbrido)* 🎬\n\n📊 *NICHO:* {nicho_usado}\n📌 *TÍTULO:* {metadata['titulo']}\n\n📝 *DESCRIPCIÓN:*\n{metadata['descripcion']}\n\n🏷️ *HASHTAGS:*\n{metadata['hashtags']}"
        
        with open(final_path, "rb") as video:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": video}, timeout=120)

    except Exception as e:
        enviar_mensaje_telegram(f"❌ *Error crítico:* {str(e)}")

if __name__ == "__main__":
    main()
