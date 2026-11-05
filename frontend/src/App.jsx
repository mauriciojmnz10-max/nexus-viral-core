import { useState, useEffect } from "react";
import "../index.css";

// Diccionario de Placeholders dinámicos por Nicho
const PLACEHOLDERS = {
  "Comida": { tema: "El mejor pan de queso de la ciudad", publico: "Adultos amantes de la comida artesanal", puntos: "Crocante por fuera, blando por dentro" },
  "Belleza": { tema: "El error que cometen todos al pedir un corte de pelo", publico: "Hombres jóvenes de 18 a 30 años", puntos: "Estilo moderno, fácil de peinar en casa" },
  "Tecnología": { tema: "El truco de privacidad que WhatsApp oculta", publico: "Usuarios de smartphone", puntos: "Configuración rápida, seguridad total" },
  "Finanzas": { tema: "Cómo ahorrar sin darte cuenta", publico: "Familias y jóvenes profesionales", puntos: "Método fácil, resultados en 30 días" },
  "Salud": { tema: "El hábito nocturno que destruye tu energía", publico: "Personas con estrés o insomnio", puntos: "Rutina de 5 minutos, mejora el sueño" },
  "Legal": { tema: "Tus derechos si te detiene la policía", publico: "Ciudadanos en general", puntos: "Explicación clara, pasos a seguir" },
  "Educación": { tema: "La técnica de estudio de la NASA", publico: "Estudiantes universitarios", puntos: "Fácil de aplicar, mejora la memoria" },
  "Fitness": { tema: "El ejercicio de 3 minutos para quemar grasa", publico: "Personas con poco tiempo", puntos: "Sin equipo, en casa, resultados rápidos" },
  "Inmobiliaria": { tema: "El error al comprar tu primera casa", publico: "Compradores primerizos", puntos: "Revisar papeles, evitar estafas" },
  "Mascotas": { tema: "La comida que mata a tu perro lentamente", publico: "Dueños de perros", puntos: "Lista de ingredientes, alternativas saludables" },
  "Viajes": { tema: "El secreto para viajar barato que las aerolíneas ocultan", publico: "Mochileros y viajeros frecuentes", puntos: "Fechas clave, trucos de reserva" },
  "Moda": { tema: "La regla de oro para combinar colores", publico: "Hombres y mujeres que quieren verse bien", puntos: "Fácil, aplicable con ropa básica" },
};

const NICHOS = Object.keys(PLACEHOLDERS);
const TONOS = ["Divertido", "Serio", "Misterioso", "Educativo", "Inspirador", "Urgente", "Profesional", "Relajado"];

export default function App() {
  const [form, setForm] = useState({ 
    negocio: "", 
    nicho: "Comida", 
    tono: "Divertido", 
    tema: "",
    publico: "",
    puntos_clave: "",
    objetivo: "Vender"
  });
  
  const [placeholders, setPlaceholders] = useState(PLACEHOLDERS["Comida"]);
  const [loading, setLoading] = useState(false);
  const [video, setVideo] = useState(null);
  const [error, setError] = useState("");

  // Actualizar placeholders cuando cambia el nicho
  useEffect(() => {
    if (PLACEHOLDERS[form.nicho]) {
      setPlaceholders(PLACEHOLDERS[form.nicho]);
    }
  }, [form.nicho]);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setVideo(null);

    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/generar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": import.meta.env.VITE_API_KEY || "Nexv1006"
        },
        body: JSON.stringify(form),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al generar");
      
      setVideo(data.video);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink-950 text-slate-300 p-6 flex flex-col items-center">
      <header className="text-center mb-10">
        <h1 className="text-4xl font-display font-bold text-gradient">Nexus Studio</h1>
        <p className="text-sm text-slate-400 mt-2">Generador de contenido viral de alta calidad</p>
      </header>

      <main className="glass w-full max-w-lg p-6 rounded-2xl">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          
          <div>
            <label className="text-xs font-semibold text-slate-400">Nombre del Negocio</label>
            <input type="text" name="negocio" required value={form.negocio} onChange={handleChange} className="input mt-1" placeholder={`Ej. ${form.nicho === 'Comida' ? 'Panadería Cucu' : 'Mi Negocio'}`} />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-semibold text-slate-400">Nicho</label>
              <select name="nicho" value={form.nicho} onChange={handleChange} className="input mt-1">
                {NICHOS.map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400">Tono</label>
              <select name="tono" value={form.tono} onChange={handleChange} className="input mt-1">
                {TONOS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400">Objetivo del Video</label>
            <select name="objetivo" value={form.objetivo} onChange={handleChange} className="input mt-1">
              <option value="Vender">Vender</option>
              <option value="Dar a conocer la marca">Marca</option>
              <option value="Educar">Educar</option>
              <option value="Entretener">Entretener</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400">Tema Central</label>
            <textarea name="tema" required rows="2" value={form.tema} onChange={handleChange} className="input mt-1" placeholder={`Ej. ${placeholders.tema}`}></textarea>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400">Público Objetivo</label>
            <input type="text" name="publico" value={form.publico} onChange={handleChange} className="input mt-1" placeholder={`Ej. ${placeholders.publico}`} />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400">Puntos Clave (Separados por comas)</label>
            <textarea name="puntos_clave" rows="2" value={form.puntos_clave} onChange={handleChange} className="input mt-1" placeholder={`Ej. ${placeholders.puntos}`}></textarea>
          </div>

          <button type="submit" disabled={loading} className="btn-primary mt-4">
            {loading ? "Generando..." : "Generar Video Ahora"}
          </button>
        </form>

        {error && <p className="text-red-400 text-sm mt-4 text-center">{error}</p>}

        {video && (
          <div className="mt-6 p-4 border border-emerald-500/30 rounded-xl bg-emerald-900/20">
            <h3 className="text-sm font-bold text-emerald-400 mb-2">✅ Video en proceso</h3>
            <p className="text-xs text-slate-300">Título: {video.titulo}</p>
            <p className="text-xs text-slate-400 mt-2">Revisa tu Telegram en unos minutos.</p>
          </div>
        )}
      </main>
    </div>
  );
}
