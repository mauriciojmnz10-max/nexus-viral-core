FROM python:3.11-slim

# Instalar FFmpeg (para video) y fuentes para los subtítulos
RUN apt-get update && apt-get install -y ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Arrancamos con Gunicorn + Uvicorn
CMD ["gunicorn", "main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "--timeout", "120"]
