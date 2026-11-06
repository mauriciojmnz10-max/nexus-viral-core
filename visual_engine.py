import requests
import logging
import os
import uuid
import time
import urllib.parse
import subprocess

log = logging.getLogger("nexus.visual")

def generar_imagen_pollinations(prompt: str, output_path: str) -> bool:
    """Genera una imagen usando Pollinations.ai con pausas para evitar el error 402."""
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&nologo=true"
        
        log.info(f"🖼️ Pidiendo imagen a Pollinations: {prompt[:40]}...")
        # Timeout más largo porque a veces el servidor tarda
        r = requests.get(url, timeout=90)
        
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(r.content)
            log.info(f"✅ Imagen generada con Pollinations exitosamente.")
            return True
        elif r.status_code == 402:
            log.warning("⚠️ Pollinations nos pidió esperar (402). Reintentando en 5s...")
            time.sleep(5)
            r = requests.get(url, timeout=90)
            if r.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                log.info(f"✅ Imagen generada en el reintento.")
                return True
            else:
                log.error(f"❌ Pollinations falló de nuevo: {r.status_code}")
                return False
        else:
            log.error(f"❌ Pollinations falló: {r.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        log.error("❌ Pollinations excedió el tiempo de espera (90s).")
        return False
    except Exception as e:
        log.error(f"❌ Excepción en Pollinations: {e}")
        return False

def procesar_imagen_a_video(img_path, output_video, duracion):
    """Aplica el efecto cinematográfico Ken Burns (Zoom) a la imagen generada."""
    try:
        temp_mp4 = output_video.replace(".mp4", "_temp.mp4")
        cmd1 = ["ffmpeg", "-y", "-loop", "1", "-i", img_path, "-t", "1", "-vf", "scale=800:1422,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", temp_mp4]
        subprocess.run(cmd1, check=True, capture_output=True)
        
        frames = int(duracion * 30)
        cmd2 = ["ffmpeg", "-y", "-i", temp_mp4, "-vf", f"zoompan=z='min(zoom+0.0015,1.5)':d={frames}:s=480x854", "-t", str(duracion), "-c:v", "libx264", "-preset", "ultrafast", output_video]
        subprocess.run(cmd2, check=True, capture_output=True)
        
        if os.path.exists(temp_mp4): os.remove(temp_mp4)
        return True
    except Exception as e:
        log.error(f"❌ Error aplicando zoom: {e}")
        return False

def obtener_clip_visual(prompt: str, work_dir: str, duracion: float) -> tuple:
    """
    Motor Visual:
    1. Genera Imagen IA (Pollinations)
    2. Le aplica zoom (Ken Burns)
    3. Retorna None si falla (para que el render use Pixabay)
    """
    # Intentamos generar la imagen IA
    img_path = os.path.join(work_dir, f"ai_img_{uuid.uuid4().hex}.jpg")
    
    # El "freno de mano": esperamos 2 segundos antes de cada petición
    time.sleep(2)
    
    if generar_imagen_pollinations(prompt, img_path):
        # Aplicar efecto de video a la imagen
        final_video = os.path.join(work_dir, f"ai_img_vid_{uuid.uuid4().hex}.mp4")
        if procesar_imagen_a_video(img_path, final_video, duracion):
            return final_video, "imagen_ia"
    
    log.warning("⚠️ Motor IA falló. Usando Pixabay (Stock) como respaldo.")
    return None, None
