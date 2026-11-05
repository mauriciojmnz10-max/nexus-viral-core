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
        if not self.gemini_key: return ""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except: return ""

    async def _call_deepseek(self, prompt: str) -> str:
        if not self.deepseek_key: return ""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.deepseek_key}"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}]}, timeout=25)
                return resp.json()["choices"][0]["message"]["content"]
            except: return ""

    async def _call_claude(self, prompt: str) -> str:
        if not self.claude_key: return ""
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": self.claude_key, "anthropic-version": "2023-06-01"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json={"model": "claude-3-haiku-20240307", "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]}, timeout=25)
                return resp.json()["content"][0]["text"]
            except: return ""

    async def _call_groq_fallback(self, prompt: str) -> str:
        if not GROQ_API_KEY: return ""
        url = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/groq/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "cf-aig-authorization": f"Bearer {CF_AUTH_TOKEN}", "Content-Type": "application/json"}
        payload = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=30)
                return resp.json()["choices"][0]["message"]["content"]
            except: return ""

    async def generar_guion_completo(self, tema: str, nicho: str) -> dict:
        log.info(f"🧠 Iniciando equipo Multi-IA para: {tema}")

        datos = await self._call_gemini(f"Dame 3 datos curiosos y reales sobre: '{tema}' (nicho: {nicho}).")
        estructura = await self._call_deepseek(f"Crea un gancho de 3s y estructura de 12 escenas basado en: {datos}")
        
        prompt_claude = f"""
        Usa esta estructura: '{estructura}'.
        Genera un guion final para YouTube Shorts.
        MUY IMPORTANTE: En el campo "visual", escribe una descripción DETALLADA EN INGLÉS de lo que se debe ver en pantalla. 
        Debe ser una escena cinematográfica, por ejemplo: "A close-up of a barber cutting hair with scissors, cinematic lighting, 4k" o "A person looking shocked at their credit card statement, dramatic lighting".
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

        if not guion_final or "{" not in guion_final:
            log.warning("⚠️ IAs avanzadas fallaron. Usando Groq Fallback.")
            guion_final = await self._call_groq_fallback(f"Genera un guion de 12 escenas sobre '{tema}'. En el campo visual escribe un prompt detallado en inglés. Devuelve SOLO JSON válido.")

        try:
            start = guion_final.find("{")
            end = guion_final.rfind("}") + 1
            return json.loads(guion_final[start:end])
        except Exception as e:
            log.error(f"Error parseando JSON: {e}")
            return None

llm_router = LLMRouter()
