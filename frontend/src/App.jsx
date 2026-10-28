import { useState } from "react";
import "./index.css";

export default function App() {
  const [form, setForm] = useState({ negocio: "", nicho: "Belleza", tono: "Divertido", tema: "" });
  const [loading, setLoading] = useState(false);
  const [video, setVideo] = useState(null);
  const [error, setError] = useState("");

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
        <p className="text-sm text-slate-400 mt-2">Generador de contenido viral para tu negocio</p>
      </header>

      <main className="glass w-full max-w-md p-6 rounded-2xl">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-xs font-semibold text-slate-400">Nombre del Negocio</label>
            <input type="text" name="negocio" required value={form.negocio} onChange={handleChange} className="input mt-1" placeholder="Ej. Peluquería Juan" />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400">Nicho</label>
            <select name="nicho" value={form.nicho} onChange={handleChange} className="input mt-1">
              <option value="Belleza">Belleza / Peluquería</option>
              <option value="Comida">Comida / Chocolatería</option>
              <option value="Tecnología">Tecnología</option>
              <option value="Finanzas">Finanzas</option>
              <option value="Misterio">Misterio</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400">Tono</label>
            <select name="tono" value={form.tono} onChange={handleChange} className="input mt-1">
              <option value="Divertido">Divertido</option>
              <option value="Serio">Serio / Profesional</option>
              <option value="Misterioso">Misterioso</option>
              <option value="Motivacional">Motivacional</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400">Tema del Video</label>
            <textarea name="tema" required rows="3" value={form.tema} onChange={handleChange} className="input mt-1" placeholder="Ej. Corte de pelo degradado, Chocolate belga..."></textarea>
          </div>

          <button type="submit" disabled={loading} className="btn-primary mt-4">
            {loading ? "Generando..." : "Generar Video Ahora"}
          </button>
        </form>

        {error && <p className="text-red-400 text-sm mt-4 text-center">{error}</p>}

        {video && (
          <div className="mt-6 p-4 border border-white/10 rounded-xl bg-ink-900/50">
            <h3 className="text-sm font-bold text-white mb-2">✅ Video en proceso</h3>
            <p className="text-xs text-slate-400">Título: {video.titulo}</p>
            <p className="text-xs text-slate-400 mt-1">Hashtags: {video.hashtags?.join(" ")}</p>
            <p className="text-xs text-emerald-400 mt-3">Revisa tu Telegram en unos minutos.</p>
          </div>
        )}
      </main>
    </div>
  );
      }
