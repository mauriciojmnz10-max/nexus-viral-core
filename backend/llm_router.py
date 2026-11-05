import httpx
import logging
import json
from config import GEMINI_API_KEY, DEEPSEEK_API_KEY, CLAUDE_API_KEY, GROQ_API_KEY, CF_AUTH_TOKEN, CF_ACCOUNT_ID, CF_GATEWAY_ID

log = logging.getLogger("nexus.llm_router")

class LLMRouter:
    def __init__(self):
        self.gemini_key = GEMINI_API_KEY
        self.deepseek_key = DEEPSEEK_API_KEY
        self.claude_key = CLAUDE_API_KEY

    def _limpiar_json(self, texto: str) -> dict:
        """Extrae el JSON de forma segura, ignorando markdown o texto extra."""
        try:
            inicio = texto.find("{")
            fin = texto.rfind("}") + 1
            if inicio != -1 and fin != 0:
                return json.loads(texto[inicio:fin])
            return None
        except Exception as e:
            log.error(f"Error parseando JSON: {e}")
            return None

    async def _call_gemini(self, prompt: str) -> str:
        if not self.gemini_key: return ""
        # Modelo actualizado a la versión estable
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_key}"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
                if resp.status_code == 200:
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    log.warning(f"Gemini falló con status {resp.status_code}: {resp.text}")
                    return ""
            except Exception as e:
                log.warning(f"Excepción en Gemini: {e}")
                return ""

    async def _call_deepseek(self, prompt: str) -> str:
        if not self.deepseek_key: return ""
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {self.deepseek_key}"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}]}, timeout=25)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                else:
                    log.warning(f"DeepSeek falló con status {resp.status_code}: {resp.text}")
                    return ""
            except Exception as e:
                log.warning(f"Excepción en DeepSeek: {e}")
                return ""

    async def _call_claude(self, prompt: str) -> str:
        if not self.claude_key: return ""
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": self.claude_key, "anthropic-version": "2023-06-01"}
        # Modelo actualizado a la versión estable de Haiku
        payload = {
            "model": "claude-3-5-haiku-20241022", 
            "max_tokens": 2000, 
            "messages": [{"role": "user", "content": prompt}]
        }
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=25)
                if resp.status_code == 200:
                    return resp.json()["content"][0]["text"]
                else:
                    log.warning(f"Claude falló con status {resp.status_code}: {resp.text}")
                    return ""
            except Exception as e:
                log.warning(f"Excepción en Claude: {e}")
                return ""

    async def _call_groq_fallback(self, prompt: str) -> str:
        if not GROQ_API_KEY: return ""
        url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}", "Content-Type": "application/json"}
        payload = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                return ""
            except: return ""

    async def generar_guion_completo(self, tema: str, nicho: str) -> dict:
        log.info(f"🧠 Iniciando equipo Multi-IA para: {tema}")

        # 1. Investigación (Gemini o Groq)
        datos = await self._call_gemini(f"Dame 3 datos curiosos y reales sobre: '{tema}' (nicho: {nicho}).")
        if not datos:
            log.warning("Gemini no respondió, usando Groq para investigación.")
            datos = await self._call_groq_fallback(f"Investiga 3 datos curiosos y reales sobre: '{tema}'.")

        # 2. Estructura (DeepSeek o Groq)
        estructura = await self._call_deepseek(f"Crea un gancho de 3s y estructura de 12 escenas basado en: {datos}")
        if not estructura:
            log.warning("DeepSeek no respondió, usando Groq para estructura.")
            estructura = await self._call_groq_fallback(f"Crea un gancho y estructura de 12 escenas basado en: {datos}")

        # 3. Redacción final (Claude o Groq)
        prompt_claude = f"""
        Usa esta estructura: '{estructura}'.
        Genera un guion final para YouTube Shorts.
        MUY IMPORTANTE: En el campo "visual", escribe una descripción DETALLADA EN INGLÉS de lo que se debe ver en pantalla. 
        Debe ser una escena cinematográfica, por ejemplo: "A close-up of a barber cutting hair with scissors, cinematic lighting, 4k".
        Devuelve SOLO un JSON válido con esta estructura exacta:
        {{
            "plataforma": "YouTube",
            "titulo": "Título adictivo",
            "descripcion": "Descripción",
            "hashtags": "#tag1 #tag2 #tag3",
            "cta_link": "CTA",
            "escenas": [
                {{"texto": "Texto de la escena (máx 15 palabras)", "visual": "Detailed english prompt for cinematic video"}}
            ]
        }}
        Asegúrate de que haya exactamente 12 escenas.
        """
        guion_final = await self._call_claude(prompt_claude)

        # 4. Fallback final a Groq
        if not guion_final or "{" not in guion_final:
            log.warning("⚠️ Claude falló. Usando Groq Fallback para el JSON final.")
            guion_final = await self._call_groq_fallback(prompt_claude)

        # 5. Limpieza y retorno seguro
        return self._limpiar_json(guion_final)

llm_router = LLMRouter()
