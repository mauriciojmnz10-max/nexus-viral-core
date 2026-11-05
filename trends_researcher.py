import os
import requests
import logging
import json
import xml.etree.ElementTree as ET
from config import GROQ_API_KEY, CF_ACCOUNT_ID, CF_GATEWAY_ID, CF_AUTH_TOKEN, TEMAS_POOL
import random

log = logging.getLogger("nexus.trends")

# URL del RSS de noticias de Google (Español - Latinoamérica)
RSS_URL = "https://news.google.com/rss?hl=es-419&gl=US&ceid=US:es-419"

def _obtener_noticias_rss() -> list:
    """Extrae los títulos de las noticias más recientes del RSS de Google."""
    noticias = []
    try:
        r = requests.get(RSS_URL, timeout=10)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title = item.find("title").text
                if title:
                    noticias.append(title)
        return noticias[:20] # Solo las top 20
    except Exception as e:
        log.error(f"Error leyendo RSS: {e}")
        return []

def _filtrar_con_groq(noticias: list, nicho: str) -> list:
    """Usa Groq para elegir las 3 noticias con más potencial viral y adaptarlas al nicho."""
    if not noticias:
        return []

    url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    # Convertimos la lista a un texto para la IA
    noticias_texto = "\n".join([f"- {n}" for n in noticias])
    
    prompt = f"""
    Aquí tienes las noticias más calientes de hoy:
    {noticias_texto}
    
    Actúa como un experto en contenido viral para TikTok/Shorts.
    Selecciona las 3 noticias que tengan MÁS potencial de morbo, curiosidad o impacto.
    Luego, adáptalas para el siguiente nicho: '{nicho}'.
    
    Devuelve SOLO un JSON válido con esta estructura exacta:
    {{
        "temas": [
            {{"tema": "Título de la noticia adaptada al nicho (máximo 15 palabras)", "nicho": "{nicho}"}},
            {{"tema": "Título de la noticia adaptada al nicho (máximo 15 palabras)", "nicho": "{nicho}"}},
            {{"tema": "Título de la noticia adaptada al nicho (máximo 15 palabras)", "nicho": "{nicho}"}}
        ]
    }}
    """
    
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        return data.get("temas", [])
    except Exception as e:
        log.error(f"Error filtrando con Groq: {e}")
        return []

def obtener_temas_autonomos(nicho_deseado: str = "general") -> list:
    """
    Función maestra. Intenta obtener tendencias reales. Si falla, usa el pool de respaldo.
    """
    log.info(f"🔍 Buscando tendencias virales para el nicho: {nicho_deseado}")
    
    noticias = _obtener_noticias_rss()
    
    if noticias:
        temas_ia = _filtrar_con_groq(noticias, nicho_deseado)
        if temas_ia and len(temas_ia) > 0:
            log.info(f"✅ Tendencias encontradas y filtradas por IA: {len(temas_ia)}")
            # Aseguramos que tengan el modo "normal"
            for t in temas_ia:
                t["modo"] = "normal"
            return temas_ia

    # --- PLAN DE RESPALDO (Si falla Google o Groq) ---
    log.warning("⚠️ Fallo la investigación de tendencias. Usando el Pool de respaldo.")
    # Filtramos el pool original por el nicho si es posible, o tomamos 3 al azar
    pool_filtrado = [t for t in TEMAS_POOL if nicho_deseado.lower() in t["nicho"].lower()]
    if not pool_filtrado:
        pool_filtrado = TEMAS_POOL.copy()
    
    random.shuffle(pool_filtrado)
    return pool_filtrado[:3]
