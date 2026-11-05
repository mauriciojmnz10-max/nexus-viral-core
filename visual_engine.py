import requests
import logging
import os
import uuid
import time

log = logging.getLogger("nexus.visual")

# Configuración de Prezzy Studio (API compatible con OpenAI)
# Nota: Para usar Prezzy, necesitas desplegar su Worker en Cloudflare o usar una instancia pública.
# Como es un proyecto open-source, si no tienes una instancia, el sistema usará Pollinations directamente.
PREZZY_BASE_URL = os.getenv("PREZZY_BASE_URL", "") # Ej: https://tu-prezzy.workers.dev/v1

def generar_video_prezzy(prompt: str, output_path: str) -> bool:
    """Intenta generar un video de 5s usando Prezzy Studio (Wan 2.2)."""
    if not PREZZY_BASE_URL:
        return False # Si no hay URL configurada, saltamos a Pollinations

    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": "wan-2-2",
            "prompt": prompt,
            "aspect_ratio": "9:16"
        }
        
        # 1. Enviar la tarea (asíncrona)
        r = requests.post(f"{PREZZY_BASE_URL}/videos/generations", headers=headers, json=payload, timeout=15)
        if r.status_code != 200:
            return False
            
        job_id = r.json().get("id")
        if not job_id:
            return False
            
        # 2. Polling para esperar el video (máx 3 minutos)
        for _ in range(36):
            time.sleep(5)
            status_r = requests.get(f"{PREZZY_BASE_URL}/jobs/{job_id}", timeout=10)
            if status_r.status_code == 200:
                data = status_r.json()
                if data.get("status") == "completed":
                    video_url = data.get("video_url")
                    if video_url:
                        # Descargar el video
                        video_data = requests.get(video_url, timeout=30).content
                        with open(output_path, "wb") as f:
                            f.write(video_data)
                        log.info(f"✅ Video generado con Prezzy: {output_path}")
                        return True
                elif data.get("status") == "failed":
                    return False
        return False
    except Exception as e:
        log.warning(f"Fallo Prezzy: {e}")
        return False

def generar_imagen_pollinations(prompt: str, output_path: str) -> bool:
    """Genera una imagen HD con Pollinations.ai (Flux) y la guarda."""
    try:
        # Pollinations usa una URL directa con el prompt codificado
        import urllib.parse
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&nologo=true"
        
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(r.content)
            log.info(f"✅ Imagen generada con Pollinations: {output_path}")
            return True
    except Exception as e:
        log.warning(f"Fallo Pollinations: {e}")
        return False

def obtener_clip_visual(prompt: str, work_dir: str, duracion: float) -> tuple:
    """
    Motor Súper Híbrido:
    1. Intenta Video IA (Prezzy)
    2. Intenta Imagen IA (Pollinations) + Ken Burns
    3. Retorna None si todo falla (para que el render use Pixabay)
    """
    # Intento 1: Video IA
    video_path = os.path.join(work_dir, f"ai_vid_{uuid.uuid4().hex}.mp4")
    if generar_video_prezzy(prompt, video_path):
        return video_path, "video_ia"
    
    # Intento 2: Imagen IA + Ken Burns
    img_path = os.path.join(work_dir, f"ai_img_{uuid.uuid4().hex}.jpg")
    if generar_imagen_pollinations(prompt, img_path):
        # Aplicar Ken Burns (Zoom)
        final_video = os.path.join(work_dir, f"ai_img_vid_{uuid.uuid4().hex}.mp4")
        try:
            import subprocess
            # Convertir imagen a video de 1s
            temp_mp4 = final_video.replace(".mp4", "_temp.mp4")
            cmd1 = ["ffmpeg", "-y", "-loop", "1", "-i", img_path, "-t", "1", "-vf", "scale=800:1422,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", temp_mp4]
            subprocess.run(cmd1, check=True, capture_output=True)
            # Aplicar zoom
            frames = int(duracion * 30)
            cmd2 = ["ffmpeg", "-y", "-i", temp_mp4, "-vf", f"zoompan=z='min(zoom+0.0015,1.5)':d={frames}:s=480x854", "-t", str(duracion), "-c:v", "libx264", "-preset", "ultrafast", final_video]
            subprocess.run(cmd2, check=True, capture_output=True)
            if os.path.exists(temp_mp4): os.remove(temp_mp4)
            return final_video, "imagen_ia"
        except:
            return None, None
            
    return None, None
