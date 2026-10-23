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

# Efectos de sonido gratuitos (URLs directas)
SFX_WHOOSH = "https://assets.mixkit.co/active_storage/sfx/2571/2571-preview.mp3"
SFX_BASS = "https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3"

def enviar_mensaje_telegram(texto):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def buscar_en_coverr(query, output):
    url = "https://api.coverr.co/videos"
    try:
        r = requests.get(url, params={"query": query, "per_page": 1, "orientation": "portrait"}, timeout=5)
        if r.status_code == 200 and r.json().get("hits"):
            video_url = r.json()["hits"][0].get("urls", {}).get("mp4_download") or r.json()["hits"][0].get("urls", {}).get("mp4")
            if video_url:
                with open(output, "wb") as f:
                    f.write(requests.get(video_url, timeout=10).content)
                return True
    except: pass
    return False

def descargar_sfx(url, output):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open(output, "wb") as f:
                f.write(r.content)
            return True
    except: pass
    return False

async def gen_audio(texto, output):
    voice = "es-ES-AlvaroNeural" 
    try:
        await asyncio.wait_for(edge_tts.Communicate(texto, voice).save(output), timeout=15)
    except Exception as e:
        raise Exception(f"Edge-TTS falló: {e}")

def main():
    work_dir = f"/tmp/nexus_{uuid.uuid4().hex}"
    os.makedirs(work_dir, exist_ok=True)

    scenes = json.loads(os.getenv("SCENES_JSON"))
    metadata = json.loads(os.getenv("METADATA_JSON"))

    try:
        # 1. Generar Audios y medir duración
        audios = []
        duraciones = []
        for i, scene in enumerate(scenes):
            audio_path = os.path.join(work_dir, f"audio_{i}.mp3")
            asyncio.run(gen_audio(scene["texto"], audio_path))
            audios.append(audio_path)
            duraciones.append(len(AudioSegment.from_file(audio_path, format="mp3")) / 1000.0)

        combined = AudioSegment.empty()
        for a in audios: combined += AudioSegment.from_file(a, format="mp3")
        audio_voz = os.path.join(work_dir, "voz_maestra.mp3")
        combined.export(audio_voz, format="mp3")

        # 2. Descargar Efectos de Sonido y mezclar
        sfx_whoosh = os.path.join(work_dir, "whoosh.mp3")
        sfx_bass = os.path.join(work_dir, "bass.mp3")
        descargar_sfx(SFX_WHOOSH, sfx_whoosh)
        descargar_sfx(SFX_BASS, sfx_bass)

        # Mezclar Voz con SFX
        audio_maestro = os.path.join(work_dir, "audio_maestro.mp3")
        if os.path.exists(sfx_whoosh) and os.path.exists(sfx_bass):
            # Mezcla simple: Voz + Whoosh (bajito) + Bass (bajito)
            cmd_mix = [
                "ffmpeg", "-y", "-i", audio_voz, "-i", sfx_whoosh, "-i", sfx_bass,
                "-filter_complex", "[1:a]volume=0.2[whoosh];[2:a]volume=0.3[bass];[0:a][whoosh][bass]amix=inputs=3:duration=first[aout]",
                "-map", "[aout]", "-c:a", "libmp3lame", "-shortest", audio_maestro
            ]
            subprocess.run(cmd_mix, check=True, capture_output=True)
        else:
            import shutil
            shutil.copy(audio_voz, audio_maestro)

        # 3. Descargar Videos (con cortes dinámicos)
        videos = []
        for i, scene in enumerate(scenes):
            dur_total = duraciones[i]
            v_path = os.path.join(work_dir, f"bg_{i}.mp4")
            
            # Si la escena dura más de 3 segundos, descargamos 2 clips y los unimos
            if dur_total > 3.0:
                v_part1 = os.path.join(work_dir, f"bg_{i}_1.mp4")
                v_part2 = os.path.join(work_dir, f"bg_{i}_2.mp4")
                buscar_en_coverr(scene["visual"], v_part1)
                buscar_en_coverr(scene["visual"] + " abstract", v_part2)
                
                if os.path.exists(v_part1) and os.path.exists(v_part2):
                    # Unir los dos clips
                    lista_txt = os.path.join(work_dir, f"lista_{i}.txt")
                    with open(lista_txt, "w") as f:
                        f.write(f"file '{v_part1}'\nfile '{v_part2}'\n")
                    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista_txt, "-c", "copy", v_path], check=True, capture_output=True)
                elif os.path.exists(v_part1):
                    os.rename(v_part1, v_path)
                else:
                    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", v_path], check=True, capture_output=True)
            else:
                buscar_en_coverr(scene["visual"], v_path)
                if not os.path.exists(v_path):
                    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "gradients=s=480x854:c0=0x1a1a2e:c1=0x000000:d=10", "-c:v", "libx264", "-preset", "ultrafast", "-t", "10", v_path], check=True, capture_output=True)
            
            videos.append(v_path)

        # 4. Generar SRT (Subtítulos cortos y con salto de línea)
        srt_path = os.path.join(work_dir, "subs.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            t = 0.0
            for i, scene in enumerate(scenes):
                dur = duraciones[i]
                texto = scene['texto']
                # Partir el texto a la mitad para que salgan 2 líneas
                palabras = texto.split()
                if len(palabras) > 4:
                    mid = len(palabras) // 2
                    texto = " ".join(palabras[:mid]) + "\\N" + " ".join(palabras[mid:])
                
                f.write(f"{i+1}\n00:00:{int(t):02},{int((t%1)*1000):03} --> 00:00:{int(t+dur):02},{int(((t+dur)%1)*1000):03}\n{texto}\n\n")
                t += dur

        # 5. Ensamblar Video Final
        inputs = []
        filter_str = ""
        for i in range(len(scenes)):
            inputs.extend(["-i", videos[i]])
            dur = duraciones[i]
            filter_str += f"[{i}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1,eq=contrast=1.2:saturation=1.3,trim=duration={dur},setpts=PTS-STARTPTS[v{i}];"

        concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
        filter_str += f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0[v];"
        
        # Estilo Hormozi: Amarillo, letras grandes, negrita
        style = "FontName=Arial,FontSize=20,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=1,Alignment=2,MarginV=150,Bold=1"
        filter_str += f"[v]subtitles={srt_path}:force_style='{style}'[vout]"

        final_path = os.path.join(work_dir, "final.mp4")
        cmd = ["ffmpeg", "-y", *inputs, "-i", audio_maestro, "-filter_complex", filter_str, "-map", "[vout]", "-map", f"{len(scenes)}:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", final_path]
        subprocess.run(cmd, check=True, capture_output=True)

        # 6. Enviar a Telegram
        caption = f"🎬 *NEXUS RENDER (Hormozi Style)* 🎬\n\n📌 *TÍTULO:* {metadata['titulo']}\n\n📝 *DESCRIPCIÓN:*\n{metadata['descripcion']}\n\n🏷️ *HASHTAGS:*\n{metadata['hashtags']}"
        
        with open(final_path, "rb") as video:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": video}, timeout=120)

    except Exception as e:
        enviar_mensaje_telegram(f"❌ *Error crítico:* {str(e)}")

if __name__ == "__main__":
    main()
