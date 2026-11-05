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

    async def _call_gemini(self, prompt: str) -> str:
        """Investigación y datos duros."""
        if not self.gemini_key: return ""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                log.warning(f"Fallo Gemini: {e}")
                return ""

    async def _call_deepseek(self, prompt: str) -> str:
        """Razonamiento crítico y estructura."""
        if not self.deepseek_key: return ""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.deepseek_key}"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}]
                }, timeout=25)
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                log.warning(f"Fallo DeepSeek: {e}")
                return ""

    async def _call_claude(self, prompt: str) -> str:
        """Redacción creativa final y hooks."""
        if not self.claude_key: return ""
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": self.claude_key, "anthropic-version": "2023-06-01"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}]
                }, timeout=25)
                return resp.json()["content"][0]["text"]
            except Exception as e:
                log.warning(f"Fallo Claude: {e}")
                return ""

    async def _call_groq_fallback(self, prompt: str) -> str:
        """El respaldo seguro que ya sabemos que funciona."""
        if not GROQ_API_KEY: return ""
        url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        payload = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=30)
                content = resp.json()["choices"][0]["message"]["content"]
                return content
            except Exception as e:
                log.error(f"Fallo Groq Fallback: {e}")
                return ""

    async def generar_guion_completo(self, tema: str, nicho: str) -> dict:
        """
        Orquesta el trabajo en equipo de las IAs.
        """
        log.info(f"🧠 Iniciando equipo Multi-IA para: {tema}")

        # PASO 1: Gemini investiga
        prompt_gemini = f"Investiga y dame 3 datos curiosos, poco conocidos y verificables sobre: '{tema}' (nicho: {nicho}). Sé breve y directo."
        datos_investigacion = await self._call_gemini(prompt_gemini)

        # PASO 2: DeepSeek estructura el gancho
        prompt_deepseek = f"Basado en estos datos: '{datos_investigacion}'. Crea un gancho de 3 segundos ultra-adictivo y define una estructura de 12 escenas cortas."
        estructura_gancho = await self._call_deepseek(prompt_deepseek)

        # PASO 3: Claude redacta el guion final y los prompts visuales
        prompt_claude = f"""
        Usa esta estructura: '{estructura_gancho}'.
        Genera un guion final para YouTube Shorts en español.
        Devuelve SOLO un JSON con esta estructura exacta:
        {{
            "plataforma": "YouTube",
            "titulo": "Título adictivo",
            "descripcion": "Descripción persuasiva",
            "hashtags": "#tag1 #tag2 #tag3",
            "cta_link": "CTA",
            "escenas": [
                {{"texto": "Texto de la escena (máx 15 palabras)", "visual": "English prompt for high quality image (e.g. 'futuristic AI robot')"}}
            ]
        }}
        Asegúrate de que haya 12 escenas.
        """
        guion_final = await self._call_claude(prompt_claude)

        # PASO 4: Fallback a Groq si todo falla
        if not guion_final or "{" not in guion_final:
            log.warning("⚠️ IAs avanzadas fallaron. Usando Groq Fallback.")
            prompt_groq = f"Genera un guion de 12 escenas sobre '{tema}'. Devuelve SOLO un JSON válido con la estructura de escenas (texto, visual)."
            guion_final = await self._call_groq_fallback(prompt_groq)

        # Limpieza de JSON
        try:
            start = guion_final.find("{")
            end = guion_final.rfind("}") + 1
            return json.loads(guion_final[start:end])
        except Exception as e:
            log.error(f"Error parseando JSON de las IAs: {e}")
            return None

llm_router = LLMRouter()
