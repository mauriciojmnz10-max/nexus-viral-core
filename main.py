import os
import subprocess
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Nexus Diagnostic")

@app.get("/")
async def root():
    return {"status": "ONLINE"}

@app.post("/diagnostico")
async def diagnostico():
    try:
        os.makedirs("/tmp/test_nexus", exist_ok=True)
        output = "/tmp/test_nexus/test.mp4"
        
        # Si el archivo existe, lo borramos
        if os.path.exists(output):
            os.remove(output)

        # Comando FFmpeg ultra-simple: video azul de 3s, sin audio
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=3",
            "-c:v", "libx264", "-preset", "ultrafast",
            output
        ]
        
        log = subprocess.run(cmd, capture_output=True, text=True)
        
        if log.returncode != 0:
            return JSONResponse(status_code=500, content={
                "status": "FFMPEG_ERROR", 
                "code": log.returncode,
                "error": log.stderr[:500]
            })
            
        return {"status": "SUCCESS", "message": "FFmpeg funciona perfectamente."}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "PYTHON_ERROR", "error": str(e)})
