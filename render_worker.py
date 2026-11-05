import os
import json
import subprocess
import requests
import uuid
import asyncio
import edge_tts
from pydub import AudioSegment
import shutil

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

MUSIC_MISTERIO = "https://assets.mixkit.co/music/preview/mixkit-mysterious-dark-and-mysterious-ambient-1005.mp3"
MUSIC_FINANZAS = "https://assets.mixkit.co/music/preview/mixkit-modern-logo-3-1191.mp3"
MUSIC_QUIZ = "https://assets.mixkit.co/music/preview/mixkit-game-level-3-2076.mp3"
SFX_WHOOSH = "https://assets.mixkit.co/active_storage/sfx/2571/2571-preview.mp3"

def enviar_mensaje_telegram(texto):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def descargar_audio(url, output):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            with open(output, "wb") as f:
                f.write(r.content)
            return True
    except: pass
    return False

def buscar_pixabay(query, output_dir, es_video=True):
    try:
        url = "https://pixabay.com/api/videos/" if es_video else "https://pixabay.com/api/"
        params = {"key": PIXABAY_API_KEY, "q": query, "per_page": 3, "orientation": "vertical", "safesearch": "true"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                if es_video:
                    video_url = hits[0].get("videos", {}).get("medium", {}).get("url") or hits[0].get("videos", {}).get("small", {}).get("url")
                    if video_url:
                        out_path = os.path.join(output_dir, f"vid_{uuid.uuid4().hex}.mp4")
                        with open(out_path, "wb") as f:
                            f.write(requests.get(video_url, timeout=20).content)
                        return out_path, True
                else:
                    img_url = hits[0].get("largeImageURL")
                    if img_url:
                        out_path = os.path.join(output_dir, f"img_{uuid.uuid4().hex}.jpg")
                        with open(out_path, "wb") as f:
                            f.write(requests.get(img_url, timeout=15).content)
                        return out_path, False
    except: pass
    return None, False

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
    except: return False

async def gen_audio(texto, output):
    # Voz más natural
    voice = "es-US-AlonsoNeural" 
    try:
        communicate = edge_tts.Communicate(texto, voice)
        await asyncio.wait_for(communicate.save(output), timeout=20)
    except Exception as e:
        raise Exception(f"Edge-TTS falló: {e}")

def main():
    work_dir = f"/tmp/nexus_{uuid.uuid4().hex}"
    os.makedirs(work_dir, exist_ok=True)

    scenes_json = os.getenv("SCENES_JSON")
    metadata_json = os.getenv("METADATA_JSON")

    if not scenes_json or scenes_json == "null": return

    scenes = json.loads(scenes_json)
    metadata = json.loads(metadata_json)
    nicho = metadata.get("nicho_usado", "").lower()

    try:
        # 1. Assets Base
        whoosh_path = os.path.join(work_dir, "whoosh.mp3")
        descargar_audio(SFX_WHOOSH, whoosh_path)
        
        music_path = os.path.join(work_dir, "music.mp3")
        if "quiz" in nicho: descargar_audio(MUSIC_QUIZ, music_path)
        elif "finanzas" in nicho or "tecnologia" in nicho: descargar_audio(MUSIC_FINANZAS, music_path)
        else: descargar_audio(MUSIC_MISTERIO, music_path)

        # 2. Audios por escena
        audios = []
        duraciones = []
        for i, scene in enumerate(scenes):
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            asyncio.run(gen_audio(scene["texto"], audio_path))
            audio_segment = AudioSegment.from_file(audio_path, format="mp3")
            audios.append(audio_path)
            duraciones.append(len(audio_segment) / 1000.0)

        # 3. Mezclar Audio (Voz + Música + SFX)
        combined = AudioSegment.empty()
        for idx, a in enumerate(audios): 
            audio_seg = AudioSegment.from_file(a, format="mp3")
            if os.path.exists(whoosh_path):
                whoosh = AudioSegment.from_file(whoosh_path, format="mp3")[:1000] - 15 
                audio_seg = whoosh + audio_seg
            combined += audio_seg
            
        audio_final = os.path.join(work_dir, "audio_maestro.mp3")
        if os.path.exists(music_path):
            musica_seg = AudioSegment.from_file(music_path, format="mp3")
            if len(musica_seg) < len(combined):
                musica_seg = musica_seg * ((len(combined) // len(musica_seg)) + 1)
            musica_seg = musica_seg[:len(combined)] - 20  # Volumen de música bajo
            mezcla = combined.overlay(musica_seg)
            mezcla.export(audio_final, format="mp3")
        else:
            combined.export(audio_final, format="mp3")

        # 4. Clips de Video
        clips = []
        for i, scene in enumerate(scenes):
            final_bg = os.path.join(work_dir, f"bg_{i}.mp4")
            dur = duraciones[i]
            query = scene["visual"]
            
            path, es_video = buscar_pixabay(query, work_dir, es_video=True)
            if es_video and path:
                cmd = ["ffmpeg", "-y", "-i", path, "-t", str(dur), "-vf", "scale=480:854:force_original_aspect_ratio=increase,crop=480:854,eq=contrast=1.2:saturation=1.3", "-c:v", "libx264", "-preset", "ultrafast", final_bg]
                subprocess.run(cmd, check=True, capture_output=True)
                clips.append(final_bg)
                continue

            path, es_video = buscar_pixabay(query, work_dir, es_video=False)
            if path:
                procesar_imagen_a_video(path, final_bg, dur)
                clips.append(final_bg)
                continue

            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", final_bg], check=True, capture_output=True)
            clips.append(final_bg)

        # 5. Subtítulos
        srt_path = os.path.join(work_dir, "subs.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            t = 0.0
            for i, scene in enumerate(scenes):
                dur = duraciones[i] + (1.0 if os.path.exists(whoosh_path) else 0.0)
                palabras = scene['texto'].split()
                bloques = [" ".join(palabras[j:j+4]) for j in range(0, len(palabras), 4)]
                tiempo_por_bloque = dur / len(bloques) if bloques else dur
                for k, bloque in enumerate(bloques):
                    start = t + (k * tiempo_por_bloque)
                    end = start + tiempo_por_bloque
                    f.write(f"{i}_{k}\n00:00:{int(start):02},{int((start%1)*1000):03} --> 00:00:{int(end):02},{int(((end)%1)*1000):03}\n{bloque}\n\n")
                t += dur

        # 6. Ensamblar Final (MAPEO DE AUDIO CORREGIDO)
        inputs = []
        filter_str = ""
        for i in range(len(scenes)):
            inputs.extend(["-i", clips[i]])
            dur = duraciones[i]
            filter_str += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,trim=duration={dur},setpts=PTS-STARTPTS[v{i}];"

        # Añadimos el audio mezclado
        inputs.extend(["-i", audio_final])
        audio_index = len(scenes)

        concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
        filter_str += f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0[v];"
        
        style = "FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=200,Bold=1"
        filter_str += f"[v]subtitles={srt_path}:force_style='{style}'[vout]"

        final_path = os.path.join(work_dir, "final.mp4")
        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_str, "-map", "[vout]", "-map", f"{audio_index}:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", final_path]
        subprocess.run(cmd, check=True, capture_output=True)

        caption = f"🎬 *NEXUS STUDIO (CINE)* 🎬\n\n📌 *Título:* {metadata['titulo']}\n📊 *Nicho:* {nicho}"
        with open(final_path, "rb") as video:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": video}, timeout=120)

    except Exception as e:
        enviar_mensaje_telegram(f"❌ *Error crítico:* {str(e)}")

if __name__ == "__main__":
    main()
