import os
import json
import subprocess
import requests
import uuid
import asyncio
import edge_tts
from pydub import AudioSegment
import urllib.parse
import shutil

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

# Música y SFX (URLs directas de Mixkit/Pixabay)
MUSIC_MISTERIO = "https://assets.mixkit.co/music/preview/mixkit-mysterious-dark-and-mysterious-ambient-1005.mp3"
MUSIC_FINANZAS = "https://assets.mixkit.co/music/preview/mixkit-modern-logo-3-1191.mp3"
MUSIC_QUIZ = "https://assets.mixkit.co/music/preview/mixkit-game-level-3-2076.mp3"
SFX_CLOCK = "https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3"

def enviar_mensaje_telegram(texto):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def descargar_fondo_base(output_path):
    try:
        url = "https://pixabay.com/api/videos/"
        params = {"key": PIXABAY_API_KEY, "q": "abstract background", "per_page": 1, "orientation": "vertical"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200 and r.json().get("hits"):
            video_url = r.json()["hits"][0].get("videos", {}).get("small", {}).get("url")
            if video_url:
                with open(output_path, "wb") as f:
                    f.write(requests.get(video_url, timeout=15).content)
                return True
    except: pass
    return False

def descargar_audio(url, output):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            with open(output, "wb") as f:
                f.write(r.content)
            return True
    except: pass
    return False

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
                        return out_path
                else:
                    img_url = hits[0].get("largeImageURL")
                    if img_url:
                        out_path = os.path.join(output_dir, f"pixabay_{uuid.uuid4().hex}.jpg")
                        with open(out_path, "wb") as f:
                            f.write(requests.get(img_url, timeout=15).content)
                        return out_path
    except: pass
    return None

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
    nicho = metadata.get("nicho_usado", "").lower()

    try:
        fondo_base_path = os.path.join(work_dir, "fondo_base.mp4")
        tiene_fondo_base = descargar_fondo_base(fondo_base_path)
        
        reloj_path = os.path.join(work_dir, "reloj.mp3")
        tiene_reloj = descargar_audio(SFX_CLOCK, reloj_path)

        # --- SELECCIÓN DE MÚSICA SEGÚN NICHO ---
        music_path = os.path.join(work_dir, "music.mp3")
        if "quiz" in nicho:
            descargar_audio(MUSIC_QUIZ, music_path)
        elif "finanzas" in nicho or "tecnologia" in nicho or "legal" in nicho:
            descargar_audio(MUSIC_FINANZAS, music_path)
        else:
            descargar_audio(MUSIC_MISTERIO, music_path)

        audios = []
        duraciones = []
        for i, scene in enumerate(scenes):
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            asyncio.run(gen_audio(scene["texto"], audio_path))
            
            audio_segment = AudioSegment.from_file(audio_path, format="mp3")
            
            if scene["texto"].strip().endswith("?") and tiene_reloj:
                print(f"[QUIZ] Añadiendo sonido de reloj a la escena {i+1}")
                reloj_segment = AudioSegment.from_file(reloj_path, format="mp3")[:5000] 
                reloj_segment = reloj_segment - 10 
                audio_segment = audio_segment + reloj_segment
                audio_segment.export(audio_path, format="mp3")
            
            audios.append(audio_path)
            duraciones.append(len(audio_segment) / 1000.0)

        combined = AudioSegment.empty()
        for a in audios: combined += AudioSegment.from_file(a, format="mp3")
        
        # --- MEZCLAR VOZ CON MÚSICA DE FONDO ---
        audio_final = os.path.join(work_dir, "audio_maestro.mp3")
        if os.path.exists(music_path):
            voz_seg = combined
            musica_seg = AudioSegment.from_file(music_path, format="mp3")
            # Repetir música hasta que cubra la duración de la voz
            if len(musica_seg) < len(voz_seg):
                repeticiones = (len(voz_seg) // len(musica_seg)) + 1
                musica_seg = musica_seg * repeticiones
            musica_seg = musica_seg[:len(voz_seg)]
            # Bajar volumen de la música al 12%
            musica_seg = musica_seg - 18 
            mezcla = voz_seg.overlay(musica_seg)
            mezcla.export(audio_final, format="mp3")
        else:
            combined.export(audio_final, format="mp3")

        clips = []
        for i, scene in enumerate(scenes):
            final_bg = os.path.join(work_dir, f"bg_{i}.mp4")
            dur = duraciones[i]
            query = scene["visual"]
            
            path = buscar_pixabay(query, work_dir, es_video=False)
            if path:
                procesar_imagen_a_video(path, final_bg, dur)
                clips.append(final_bg)
                continue

            path = buscar_pixabay(query, work_dir, es_video=True)
            if path:
                os.rename(path, final_bg)
                clips.append(final_bg)
                continue

            if tiene_fondo_base:
                shutil.copy(fondo_base_path, final_bg)
                clips.append(final_bg)
            else:
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", final_bg], check=True, capture_output=True)
                clips.append(final_bg)

        srt_path = os.path.join(work_dir, "subs.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            t = 0.0
            for i, scene in enumerate(scenes):
                dur = duraciones[i]
                palabras = scene['texto'].split()
                bloques = [" ".join(palabras[j:j+4]) for j in range(0, len(palabras), 4)]
                tiempo_por_bloque = dur / len(bloques) if bloques else dur
                
                for k, bloque in enumerate(bloques):
                    start = t + (k * tiempo_por_bloque)
                    end = start + tiempo_por_bloque
                    if " A)" in bloque or " B)" in bloque:
                        bloque = bloque.replace(" A)", "\NA)").replace(" B)", "\NB)").replace(" C)", "\NC)")
                    
                    f.write(f"{i}_{k}\n00:00:{int(start):02},{int((start%1)*1000):03} --> 00:00:{int(end):02},{int(((end)%1)*1000):03}\n{bloque}\n\n")
                t += dur

        inputs = []
        filter_str = ""
        for i in range(len(scenes)):
            inputs.extend(["-i", clips[i]])
            dur = duraciones[i]
            if os.path.basename(clips[i]) == "bg_" + str(i) + ".mp4" and tiene_fondo_base and "pixabay" not in clips[i]:
                filter_str += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,loop=-1:size=1,trim=duration={dur},setpts=PTS-STARTPTS[v{i}];"
            else:
                filter_str += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,trim=duration={dur},setpts=PTS-STARTPTS[v{i}];"

        concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
        filter_str += f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0[v];"
        
        style = "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=150,Bold=1"
        filter_str += f"[v]subtitles={srt_path}:force_style='{style}'[vout]"

        final_path = os.path.join(work_dir, "final.mp4")
        cmd = ["ffmpeg", "-y", *inputs, "-i", audio_final, "-filter_complex", filter_str, "-map", "[vout]", "-map", f"{len(scenes)}:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", final_path]
        subprocess.run(cmd, check=True, capture_output=True)

        nicho_usado = metadata.get("nicho_usado", "No especificado")
        caption = f"🎬 *NEXUS RENDER (Cinematic Shield)* 🎬\n\n📊 *NICHO:* {nicho_usado}\n📌 *TÍTULO:* {metadata['titulo']}\n\n📝 *DESCRIPCIÓN:*\n{metadata['descripcion']}\n\n🏷️ *HASHTAGS:*\n{metadata['hashtags']}"
        
        with open(final_path, "rb") as video:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": video}, timeout=120)

    except Exception as e:
        enviar_mensaje_telegram(f"❌ *Error crítico:* {str(e)}")

if __name__ == "__main__":
    main()
