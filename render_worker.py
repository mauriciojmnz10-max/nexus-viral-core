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

def descargar_imagen_wikipedia(query, output):
    """Busca imágenes reales en Wikipedia basadas en el texto."""
    try:
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(query)}&prop=pageimages&format=json&pithumbsize=1000"
        r = requests.get(search_url, timeout=10).json()
        pages = r.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if "thumbnail" in page_data:
                img_url = page_data["thumbnail"]["source"]
                with open(output, "wb") as f:
                    f.write(requests.get(img_url, timeout=15).content)
                print(f"[WIKI] Imagen encontrada para: {query}")
                return True
    except Exception as e:
        print(f"[WIKI] Error: {e}")
    return False

def descargar_clip_coverr(query, output):
    """Respaldo: Video de Coverr si Wikipedia falla."""
    try:
        url = "https://api.coverr.co/videos"
        r = requests.get(url, params={"query": query, "per_page": 1, "orientation": "portrait"}, timeout=5)
        if r.status_code == 200 and r.json().get("hits"):
            video_url = r.json()["hits"][0].get("urls", {}).get("mp4_download") or r.json()["hits"][0].get("urls", {}).get("mp4")
            if video_url:
                with open(output, "wb") as f:
                    f.write(requests.get(video_url, timeout=15).content)
                print(f"[COVERR] Video encontrado para: {query}")
                return True
    except: pass
    return False

async def gen_audio(texto, output):
    voice = "es-ES-ElviraNeural" # Voz femenina más natural
    try:
        # Añadimos un rate del 10% para que sea más dinámica
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
        # 1. Generar Audios
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

        # 2. Descargar Imágenes/Videos (Híbrido)
        clips = []
        for i, scene in enumerate(scenes):
            img_path = os.path.join(work_dir, f"img_{i}.jpg")
            vid_path = os.path.join(work_dir, f"vid_{i}.mp4")
            final_bg = os.path.join(work_dir, f"bg_{i}.mp4")
            
            # 1. Intentar Wikipedia (Imagen real con zoom)
            exito_wiki = descargar_imagen_wikipedia(scene["visual"], img_path)
            
            if exito_wiki:
                dur = duraciones[i]
                # Efecto Ken Burns (Zoom sobre imagen estática)
                cmd_zoom = [
                    "ffmpeg", "-y", "-loop", "1", "-i", img_path,
                    "-vf", f"scale=800:1422,zoompan=z='min(zoom+0.0015,1.5)':d={int(dur*30)}:s=480x854",
                    "-t", str(dur), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", final_bg
                ]
                subprocess.run(cmd_zoom, check=True, capture_output=True)
            else:
                # 2. Intentar Coverr (Video de stock)
                if not descargar_clip_coverr(scene["visual"], vid_path):
                    # 3. Fondo de gradiente si todo falla
                    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", vid_path], check=True, capture_output=True)
                os.rename(vid_path, final_bg)
            
            clips.append(final_bg)

        # 3. Generar SRT (Subtítulos cortos, blancos, 3 palabras por bloque)
        srt_path = os.path.join(work_dir, "subs.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            t = 0.0
            for i, scene in enumerate(scenes):
                dur = duraciones[i]
                palabras = scene['texto'].split()
                
                # Dividir en bloques de máximo 3 palabras para que salgan rápido
                bloques = [" ".join(palabras[j:j+3]) for j in range(0, len(palabras), 3)]
                tiempo_por_bloque = dur / len(bloques) if bloques else dur
                
                for k, bloque in enumerate(bloques):
                    start = t + (k * tiempo_por_bloque)
                    end = start + tiempo_por_bloque
                    f.write(f"{i}_{k}\n00:00:{int(start):02},{int((start%1)*1000):03} --> 00:00:{int(end):02},{int(((end)%1)*1000):03}\n{bloque}\n\n")
                
                t += dur

        # 4. Ensamblar Video Final
        inputs = []
        filter_str = ""
        for i in range(len(scenes)):
            inputs.extend(["-i", clips[i]])
            dur = duraciones[i]
            filter_str += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,trim=duration={dur},setpts=PTS-STARTPTS[v{i}];"

        concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
        filter_str += f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0[v];"
        
        # Estilo Blanco, más pequeño (14) y bold
        style = "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=150,Bold=1"
        filter_str += f"[v]subtitles={srt_path}:force_style='{style}'[vout]"

        final_path = os.path.join(work_dir, "final.mp4")
        cmd = ["ffmpeg", "-y", *inputs, "-i", audio_maestro, "-filter_complex", filter_str, "-map", "[vout]", "-map", f"{len(scenes)}:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", final_path]
        subprocess.run(cmd, check=True, capture_output=True)

        caption = f"🎬 *NEXUS RENDER (Híbrido)* 🎬\n\n📌 *TÍTULO:* {metadata['titulo']}\n\n📝 *DESCRIPCIÓN:*\n{metadata['descripcion']}\n\n🏷️ *HASHTAGS:*\n{metadata['hashtags']}"
        
        with open(final_path, "rb") as video:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": video}, timeout=120)

    except Exception as e:
        enviar_mensaje_telegram(f"❌ *Error crítico:* {str(e)}")

if __name__ == "__main__":
    main()
