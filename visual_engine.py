import requests
import logging
import os
import uuid
import time
import urllib.parse

log = logging.getLogger("nexus.visual")

PREZZY_BASE_URL = os.getenv("PREZZY_BASE_URL", "")

def generar_video_prezzy(prompt: str, output_path: str) -> bool:
    if not PREZZY_BASE_URL:
        log.warning("⚠️ PREZZY_BASE_URL no está configurada. Saltando Prezzy.")
        return False

    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": "wan-2-2",
            "prompt": prompt,
            "aspect_ratio": "9:16"
        }
        
        log.info(f"🎬 Pidiendo video a Prezzy: {prompt[:30]}...")
        r = requests.post(f"{PREZZY_BASE_URL}/v1/videos/generations", headers=headers, json=payload, timeout=15)
        
        if r.status_code != 200:
            log.error(f"❌ Prezzy falló al crear tarea: {r.status_code} - {r.text}")
            return False
            
        job_id = r.json().get("id")
        if not job_id:
            log.error(f"❌ Prezzy no devolvió ID de tarea: {r.text}")
            return False
            
        for _ in range(36): # 3 minutos máximo
            time.sleep(5)
            status_r = requests.get(f"{PREZZY_BASE_URL}/v1/jobs/{job_id}", timeout=10)
            if status_r.status_code == 200:
                data = status_r.json()
                if data.get("status") == "completed":
                    video_url = data.get("video_url")
                    if video_url:
                        video_data = requests.get(video_url, timeout=30).content
                        with open(output_path, "wb") as f:
                            f.write(video_data)
                        log.info(f"✅ Video generado con Prezzy exitosamente.")
                        return True
                elif data.get("status") == "failed":
                    log.error(f"❌ Prezzy reportó tarea fallida: {data}")
                    return False
        log.warning("⚠️ Prezzy excedió el tiempo de espera.")
        return False
    except Exception as e:
        log.error(f"❌ Excepción en Prezzy: {e}")
        return False

def generar_imagen_pollinations(prompt: str, output_path: str) -> bool:
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&nologo=true"
        log.info(f"🖼️ Pidiendo imagen a Pollinations: {prompt[:30]}...")
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(r.content)
            log.info(f"✅ Imagen generada con Pollinations exitosamente.")
            return True
        else:
            log.error(f"❌ Pollinations falló: {r.status_code}")
    except Exception as e:
        log.error(f"❌ Excepción en Pollinations: {e}")
    return False

def obtener_clip_visual(prompt: str, work_dir: str, duracion: float) -> tuple:
    # 1. Intentar Video IA
    video_path = os.path.join(work_dir, f"ai_vid_{uuid.uuid4().hex}.mp4")
    if generar_video_prezzy(prompt, video_path):
        return video_path, "video_ia"
    
    # 2. Intentar Imagen IA + Ken Burns
    img_path = os.path.join(work_dir, f"ai_img_{uuid.uuid4().hex}.jpg")
    if generar_imagen_pollinations(prompt, img_path):
        final_video = os.path.join(work_dir, f"ai_img_vid_{uuid.uuid4().hex}.mp4")
        try:
            import subprocess
            temp_mp4 = final_video.replace(".mp4", "_temp.mp4")
            cmd1 = ["ffmpeg", "-y", "-loop", "1", "-i", img_path, "-t", "1", "-vf", "scale=800:1422,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", temp_mp4]
            subprocess.run(cmd1, check=True, capture_output=True)
            frames = int(duracion * 30)
            cmd2 = ["ffmpeg", "-y", "-i", temp_mp4, "-vf", f"zoompan=z='min(zoom+0.0015,1.5)':d={frames}:s=480x854", "-t", str(duracion), "-c:v", "libx264", "-preset", "ultrafast", final_video]
            subprocess.run(cmd2, check=True, capture_output=True)
            if os.path.exists(temp_mp4): os.remove(temp_mp4)
            return final_video, "imagen_ia"
        except Exception as e:
            log.error(f"❌ Error aplicando zoom a imagen IA: {e}")
            return None, None
            
    log.warning("⚠️ Motor IA falló por completo. Usando Pixabay (Stock).")
    return None, None
