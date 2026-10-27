// Capa de acceso a la API de Nexus Studio.
// Toda la configuración viene de variables VITE_* (ver .env.example).

const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
const API_KEY = import.meta.env.VITE_API_KEY ?? "";
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

export class ApiError extends Error {
  constructor(message, { status = 0, campos = [] } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.campos = campos;
  }
}

async function request(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("No se pudo conectar con el servidor. Revisa tu conexión.");
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    /* respuesta sin cuerpo JSON */
  }

  if (!res.ok) {
    throw new ApiError(data?.error ?? `Error inesperado del servidor (${res.status}).`, {
      status: res.status,
      campos: data?.campos ?? [],
    });
  }
  return data;
}

/* ------------------------------ Modo demo ------------------------------- */
// Simula el backend en memoria para poder enseñar el dashboard a clientes
// sin servidor. Actívalo con VITE_DEMO_MODE=true.

const demoDb = [];
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const demoId = () => Math.random().toString(36).slice(2, 14);

async function demoGenerar(datos) {
  await wait(700);
  const tema = datos.tema.split(",")[0].trim();
  const video = {
    id: demoId(),
    ...datos,
    titulo: tema,
    hashtags: ["#" + datos.nicho.replace(/\s+/g, ""), "#viral", "#fyp", "#shorts"],
    estado: "procesando",
    creado: new Date().toISOString(),
    telegram_url: null,
    download_url: null,
    error: null,
  };
  demoDb.unshift(video);
  setTimeout(() => {
    video.estado = "listo";
    video.titulo = `${tema.charAt(0).toUpperCase()}${tema.slice(1)}: lo que nadie te cuenta`;
    video.telegram_url = "https://t.me/";
  }, 9000);
  return { ok: true, mensaje: "Video en proceso.", job_id: video.id, video: { ...video } };
}

/* ------------------------------ API pública ----------------------------- */

export async function generarVideo(datos) {
  if (DEMO_MODE) return demoGenerar(datos);
  return request("/api/generar", { method: "POST", body: datos });
}

export async function listarVideos() {
  if (DEMO_MODE) return demoDb.map((v) => ({ ...v }));
  const data = await request("/api/videos");
  return data.videos;
}
