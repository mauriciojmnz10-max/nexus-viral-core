import httpx
import logging
from config import settings

log = logging.getLogger("nexus.llm_router")

class LLMRouter:
    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY
        self.deepseek_key = settings.DEEPSEEK_API_KEY
        self.claude_key = settings.CLAUDE_API_KEY

    async def _call_gemini(self, prompt: str) -> str:
        """Investigación y volumen masivo de datos."""
        if not self.gemini_key: return "Error: Gemini API Key no configurada."
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                log.error(f"Error en Gemini: {e}")
                return "Error de conexión con Gemini."

    async def _call_deepseek(self, prompt: str) -> str:
        """Razonamiento lógico, crítica y análisis de tendencias."""
        if not self.deepseek_key: return "Error: DeepSeek API Key no configurada."
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.deepseek_key}"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}]
                }, timeout=30)
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                log.error(f"Error en DeepSeek: {e}")
                return "Error de conexión con DeepSeek."

    async def _call_claude(self, prompt: str) -> str:
        """Redacción creativa, guiones y hooks virales."""
        if not self.claude_key: return "Error: Claude API Key no configurada."
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": self.claude_key, "anthropic-version": "2023-06-01"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}]
                }, timeout=30)
                return resp.json()["content"][0]["text"]
            except Exception as e:
                log.error(f"Error en Claude: {e}")
                return "Error de conexión con Claude."

    async def route(self, task_type: str, prompt: str) -> str:
        """Enruta la tarea al modelo correcto de forma asíncrona."""
        if task_type == "investigacion":
            return await self._call_gemini(prompt)
        elif task_type == "critica":
            return await self._call_deepseek(prompt)
        elif task_type == "redaccion":
            return await self._call_claude(prompt)
        else:
            return await self._call_gemini(prompt) # Por defecto

# Instancia global
llm_router = LLMRouter()
