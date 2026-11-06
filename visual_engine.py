import requests
import logging
import os
import uuid
import time
import urllib.parse
import subprocess

log = logging.getLogger("nexus.visual")

HF_TOKEN = os.getenv("HUGGINGFACE_API_KEY", "").strip()
# URL ACTUALIZADA AL NUEVO ROUTER DE HUGGING FACE
HF_URL = "https://router.huggingface.co/v1/images/generations"
HF_MODEL = "black-forest-labs/FLUX.1-schnell"

def generar_imagen_ia(prompt: str, output_path: str) -> bool:
    """Genera una imagen hiperrealista usando FLUX a través del nuevo Router de Hugging Face."""
    if not HF_TOKEN:
        log.warning("⚠️ HUGGINGFACE_API_KEY no configurada. Saltando generación IA.")
        return False

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }
    # La nueva API de imágenes usa un payload con 'model' y 'prompt'
    payload = {
        "model": HF_MODEL,
        "prompt": prompt,
        "response_format": "b64_json"  # Pedimos la imagen en base64 para descargarla
    }

    # Intentamos hasta 3 veces (por si el modelo está cargando)
    for intento in range(3):
        try:
            log.info(f"🖼️ Pidiendo imagen a FLUX (Intento {intento+1}): {prompt[:40]}...")
            r = requests.post(HF_URL, headers=headers, json=payload, timeout=60)
            
            if r.status_code == 200:
                data = r.json()
                # La nueva API devuelve la imagen en un array de 'data'
                image_b64 = data.get("data", [{}])[0].get("b64_json")
                if image_b64:
                    import base64
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(image_b64))
                    log.info(f"✅ Imagen IA generada exitosamente.")
                    return True
                else:
                    log.error(f"❌ Hugging Face no devolvió la imagen esperada: {data}")
                    return False
            
            elif r.status_code == 503:
                log.warning("⏳ Modelo FLUX cargando. Esperando 10 segundos...")
                time.sleep(10)
            else:
                log.error(f"❌ Hugging Face falló: {r.status_code} - {r.text[:150]}")
                return False
        except Exception as e:
            log.error(f"❌ Excepción en Hugging Face: {e}")
            time.sleep(5)

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
    1. Genera Imagen IA (FLUX)
    2. Le aplica zoom (Ken Burns)
    3. Retorna None si falla (para que el render use Pixabay)
    """
    # Intentamos generar la imagen IA
    img_path = os.path.join(work_dir, f"ai_img_{uuid.uuid4().hex}.jpg")
    if generar_imagen_ia(prompt, img_path):
        # Aplicar efecto de video a la imagen
        final_video = os.path.join(work_dir, f"ai_img_vid_{uuid.uuid4().hex}.mp4")
        if procesar_imagen_a_video(img_path, final_video, duracion):
            return final_video, "imagen_ia"
    
    log.warning("⚠️ Motor IA falló. Usando Pixabay (Stock) como respaldo.")
    return None, None
