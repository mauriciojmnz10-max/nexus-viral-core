import os
from dotenv import load_dotenv

load_dotenv()

# --- CREDENCIALES ---
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
GITHUB_OWNER = (os.getenv("GITHUB_OWNER") or "").strip()
GITHUB_REPO = (os.getenv("GITHUB_REPO") or "").strip()

CF_ACCOUNT_ID = "ead76709dc92c64a480ffca88bbc1b29"
CF_GATEWAY_ID = "i-a" 
CF_AUTH_TOKEN = (os.getenv("CF_AUTH_TOKEN") or "").strip()

# --- POOL DE TEMAS ---
TEMAS_POOL = [
    # Finanzas
    {"tema": "El error de las tarjetas de crédito", "nicho": "finanzas", "modo": "normal"},
    {"tema": "Cómo ahorrar sin darte cuenta", "nicho": "finanzas", "modo": "normal"},
    {"tema": "La trampa de los préstamos rápidos", "nicho": "finanzas", "modo": "normal"},
    {"tema": "El interés compuesto explicado en 60s", "nicho": "finanzas", "modo": "normal"},
    {"tema": "Por qué los ricos no tienen deudas", "nicho": "finanzas", "modo": "normal"},
    # Tecnología / IA
    {"tema": "La IA que te quitará el trabajo", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "El gadget que ahorra energía", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "Cómo proteger tu privacidad en internet", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "El futuro de los coches autónomos", "nicho": "tecnologia", "modo": "normal"},
    {"tema": "La verdad sobre el 5G", "nicho": "tecnologia", "modo": "normal"},
    # Legal / Derecho
    {"tema": "Tus derechos si te detiene la policía", "nicho": "legal", "modo": "normal"},
    {"tema": "El error legal al firmar un contrato", "nicho": "legal", "modo": "normal"},
    {"tema": "Cómo reclamar una multa injusta", "nicho": "legal", "modo": "normal"},
    # Salud / Bienestar
    {"tema": "El hábito que destruye tu sueño", "nicho": "salud", "modo": "normal"},
    {"tema": "Por qué el azúcar oculto te enferma", "nicho": "salud", "modo": "normal"},
    {"tema": "La verdad sobre las dietas milagro", "nicho": "salud", "modo": "normal"},
    # Psicología Oscura
    {"tema": "Cómo manipulan tu mente los anuncios", "nicho": "psicologia", "modo": "normal"},
    {"tema": "El sesgo cognitivo que te hace gastar", "nicho": "psicologia", "modo": "normal"},
    {"tema": "La técnica de persuasión de la CIA", "nicho": "psicologia", "modo": "normal"},
    # Motivación / Éxito
    {"tema": "La regla de los 5 segundos para vencer la pereza", "nicho": "motivacion", "modo": "normal"},
    {"tema": "Cómo levantarte a las 5 AM sin morir", "nicho": "motivacion", "modo": "normal"},
    {"tema": "El secreto de los estoicos para ser feliz", "nicho": "motivacion", "modo": "normal"},
    # Historia / Crímenes
    {"tema": "El secreto oculto de la Gran Muralla China", "nicho": "historia", "modo": "normal"},
    {"tema": "El crimen que cambió la historia de Roma", "nicho": "historia", "modo": "normal"},
    {"tema": "La verdad sobre Jack el Destripador", "nicho": "historia", "modo": "normal"},
    # Misterio / Ciencia
    {"tema": "El código oculto en la Mona Lisa", "nicho": "misterio", "modo": "normal"},
    {"tema": "El Triángulo de las Bermudas: la verdad", "nicho": "misterio", "modo": "normal"},
    {"tema": "¿Qué hay dentro de un agujero negro?", "nicho": "ciencia", "modo": "normal"},
    {"tema": "El experimento de la prisión de Stanford", "nicho": "ciencia", "modo": "normal"},
    # Quiz
    {"tema": "Quiz: ¿Cuánto sabes de historia universal?", "nicho": "cultura general", "modo": "quiz"},
    {"tema": "Quiz: Adivina el país por su bandera", "nicho": "geografia", "modo": "quiz"},
    {"tema": "Quiz: Preguntas de ciencia básica", "nicho": "ciencia", "modo": "quiz"},
    {"tema": "Quiz: ¿Cuánto sabes de cine?", "nicho": "cine", "modo": "quiz"},
    {"tema": "Quiz: Preguntas de cultura pop", "nicho": "cultura pop", "modo": "quiz"},
    {"tema": "Quiz: Matemáticas rápidas", "nicho": "matematicas", "modo": "quiz"}
]
