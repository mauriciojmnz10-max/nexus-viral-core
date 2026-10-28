import { useEffect, useState } from "react";
import { DEMO_MODE, generarVideo, listarVideos } from "./api";

/* ------------------------------ Constantes ------------------------------ */

const NICHOS = [
  "Comida",
  "Belleza",
  "Tecnología",
  "Moda",
  "Fitness",
  "Mascotas",
  "Inmobiliaria",
  "Educación",
  "Otro",
];
const TONOS = ["Divertido", "Serio", "Misterioso", "Inspirador", "Educativo"];
const EJEMPLOS = ["Corte de pelo degradado", "Chocolate belga", "Rutina de skincare"];
const PASOS = [
  "Analizando tu marca",
  "Escribiendo el guion con IA",
  "Buscando clips y música",
  "Renderizando el video",
  "Subiendo a Telegram",
];

const POLL_MS = 3000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const STEP_MS = 4000;
const BRAND_KEY = "nexus.brand";

const FORM_INICIAL = { negocio: "", nicho: "Comida", tono: "Divertido", tema: "" };

/* ------------------------------- Utilidades ----------------------------- */

function cargarMarca() {
  try {
    const saved = JSON.parse(localStorage.getItem(BRAND_KEY) ?? "{}");
    return {
      ...FORM_INICIAL,
      negocio: typeof saved.negocio === "string" ? saved.negocio : "",
      nicho: NICHOS.includes(saved.nicho) ? saved.nicho : FORM_INICIAL.nicho,
      tono: TONOS.includes(saved.tono) ? saved.tono : FORM_INICIAL.tono,
    };
  } catch {
    return FORM_INICIAL;
  }
}

function validar(f) {
  const errores = {};
  if (f.negocio.trim().length < 2) errores.negocio = "Escribe el nombre de tu negocio.";
  if (f.tema.trim().length < 3) errores.tema = "Indica al menos un tema o palabra clave.";
  return errores;
}

function tiempoRelativo(iso) {
  const seg = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seg < 60) return "hace un momento";
  if (seg < 3600) return `hace ${Math.floor(seg / 60)} min`;
  if (seg < 86400) return `hace ${Math.floor(seg / 3600)} h`;
  return new Date(iso).toLocaleDateString("es", { day: "numeric", month: "short" });
}

/* --------------------------------- Iconos ------------------------------- */

const iconProps = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

const IconSpark = (p) => (
  <svg {...iconProps} {...p}>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" />
    <path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16z" />
  </svg>
);
const IconDownload = (p) => (
  <svg {...iconProps} {...p}>
    <path d="M12 3v12m0 0l-4-4m4 4l4-4M4 20h16" />
  </svg>
);
const IconSend = (p) => (
  <svg {...iconProps} {...p}>
    <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
  </svg>
);
const IconCheck = (p) => (
  <svg {...iconProps} {...p}>
    <path d="M20 6L9 17l-5-5" />
  </svg>
);
const IconFilm = (p) => (
  <svg {...iconProps} {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4" />
  </svg>
);

/* ------------------------------ Componentes ----------------------------- */

function Header({ online }) {
  const estado = DEMO_MODE
    ? { texto: "Modo demo", clase: "bg-amber-400", texto2: "text-amber-300" }
    : online === null
      ? { texto: "Conectando…", clase: "bg-slate-500", texto2: "text-slate-400" }
      : online
        ? { texto: "Motor en línea", clase: "bg-emerald-400", texto2: "text-emerald-300" }
        : { texto: "Sin conexión", clase: "bg-rose-500", texto2: "text-rose-300" };

  return (
    <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 pt-6 sm:px-8">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-neon-cyan via-neon-violet to-neon-pink text-white shadow-lg shadow-neon-violet/30">
          <IconSpark width={20} height={20} />
        </div>
        <div className="leading-tight">
          <p className="font-display text-lg font-bold tracking-tight text-white">
            NEXUS <span className="text-gradient">STUDIO</span>
          </p>
          <p className="text-xs text-slate-500">Centro de control</p>
        </div>
      </div>
      <div className="glass flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs">
        <span className={`h-2 w-2 rounded-full ${estado.clase}`} />
        <span className={estado.texto2}>{estado.texto}</span>
      </div>
    </header>
  );
}

function Field({ id, label, hint, error, children }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-slate-200">
          {label}
        </label>
        {hint && <span className="text-xs text-slate-500">{hint}</span>}
      </div>
      {children}
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-xs text-rose-400">
          {error}
        </p>
      )}
    </div>
  );
}

function PhonePreview({ status, form, step, video }) {
  const marca = form.negocio.trim() || "Tu negocio";
  const tema = form.tema.trim().split(",")[0] || "Tu próximo video viral";
  const listo = status === "done" && video;

  return (
    <div className="relative mx-auto w-full max-w-[260px] animate-float">
      <div className="relative aspect-[9/16] overflow-hidden rounded-[2.2rem] border border-white/10 bg-ink-900 shadow-[0_0_70px_-20px_rgba(139,92,246,0.55)]">
        <div className="grid-bg absolute inset-0" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_30%,rgba(139,92,246,0.28),transparent_60%),linear-gradient(180deg,transparent_40%,rgba(5,6,10,0.92))]" />

        {/* Notch */}
        <div className="absolute left-1/2 top-2.5 h-1.5 w-16 -translate-x-1/2 rounded-full bg-black/70" />

        {/* Barra lateral estilo Shorts */}
        <div className="absolute bottom-24 right-3 flex flex-col items-center gap-3 opacity-70">
          {[0, 1, 2].map((i) => (
            <span key={i} className="h-7 w-7 rounded-full border border-white/20 bg-white/10" />
          ))}
        </div>

        {/* Estado: generando */}
        {status === "loading" && (
          <>
            <div className="absolute inset-x-0 top-0 h-10 animate-scan bg-gradient-to-b from-transparent via-neon-cyan/35 to-transparent" />
            <div className="absolute inset-x-0 top-[38%] px-6 text-center" aria-live="polite">
              <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-white/15 border-t-neon-cyan" />
              <p className="font-display text-sm font-semibold text-white">{PASOS[step]}</p>
              <p className="mt-1 text-[11px] text-slate-400">
                Paso {step + 1} de {PASOS.length}
              </p>
              <div className="mx-auto mt-4 h-1 w-32 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-neon-cyan to-neon-violet transition-all duration-700"
                  style={{ width: `${((step + 1) / PASOS.length) * 100}%` }}
                />
              </div>
            </div>
          </>
        )}

        {/* Estado: reposo / listo / error */}
        {status !== "loading" && (
          <div className="absolute inset-x-0 top-[34%] px-6 text-center">
            {listo ? (
              <span className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-emerald-400/15 text-emerald-300 ring-1 ring-emerald-400/40">
                <IconCheck width={20} height={20} />
              </span>
            ) : (
              <span className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-white/5 text-slate-400 ring-1 ring-white/10">
                <IconFilm width={20} height={20} />
              </span>
            )}
            <p className="font-display text-sm font-semibold text-white">
              {listo ? "¡Video listo!" : status === "error" ? "No se pudo generar" : "Vista previa 9:16"}
            </p>
            <p className="mt-1 text-[11px] text-slate-400">
              {listo
                ? "Ya está en tu Telegram."
                : status === "error"
                  ? "Revisa el mensaje e inténtalo otra vez."
                  : "Así se verá tu próximo video."}
            </p>
          </div>
        )}

        {/* Pie estilo TikTok */}
        <div className="absolute inset-x-0 bottom-0 p-4 pr-14">
          <p className="truncate text-xs font-semibold text-white">@{marca.replace(/\s+/g, "").toLowerCase()}</p>
          <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-200">
            {listo ? video.titulo : tema}
          </p>
          <p className="mt-1 truncate text-[10px] text-neon-cyan">
            {listo && video.hashtags?.length
              ? video.hashtags.slice(0, 4).join(" ")
              : `#${form.nicho.replace(/\s+/g, "")} #viral #fyp`}
          </p>
        </div>
      </div>
    </div>
  );
}

const BADGES = {
  procesando: { texto: "Procesando", clase: "bg-amber-400/10 text-amber-300 ring-amber-400/30" },
  listo: { texto: "Listo", clase: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/30" },
  error: { texto: "Error", clase: "bg-rose-500/10 text-rose-300 ring-rose-500/30" },
};

function AccionLink({ href, icon, children }) {
  const activo = Boolean(href);
  return (
    <a
      className="btn-ghost"
      href={activo ? href : undefined}
      target="_blank"
      rel="noopener noreferrer"
      aria-disabled={!activo}
      onClick={(e) => !activo && e.preventDefault()}
    >
      {icon}
      {children}
    </a>
  );
}

function VideoList({ videos }) {
  return (
    <section className="glass rounded-2xl p-5 sm:p-6" aria-labelledby="ultimos-titulo">
      <div className="mb-4 flex items-center justify-between">
        <h2 id="ultimos-titulo" className="font-display text-base font-semibold text-white">
          Últimos videos
        </h2>
        <span className="text-xs text-slate-500">{videos.length} en total</span>
      </div>

      {videos.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 px-4 py-10 text-center">
          <p className="text-sm text-slate-400">Aún no has generado videos.</p>
          <p className="mt-1 text-xs text-slate-600">Completa el formulario y pulsa “Generar video ahora”.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {videos.map((v) => {
            const badge = BADGES[v.estado] ?? BADGES.procesando;
            const listo = v.estado === "listo";
            return (
              <li key={v.id} className="rounded-xl border border-white/[0.07] bg-ink-900/60 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-white">{v.titulo}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {v.negocio} · {tiempoRelativo(v.creado)}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${badge.clase}`}
                  >
                    {badge.texto}
                  </span>
                </div>

                {v.hashtags?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {v.hashtags.map((h) => (
                      <span key={h} className="rounded-md bg-white/5 px-2 py-0.5 text-[11px] text-neon-cyan/90">
                        {h}
                      </span>
                    ))}
                  </div>
                )}

                {v.estado === "error" && v.error && (
                  <p className="mt-3 text-xs text-rose-400">{v.error}</p>
                )}

                {listo && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <AccionLink href={v.download_url} icon={<IconDownload width={14} height={14} />}>
                      Descargar
                    </AccionLink>
                    <AccionLink href={v.telegram_url} icon={<IconSend width={14} height={14} />}>
                      Ver en Telegram
                    </AccionLink>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/* ---------------------------------- App --------------------------------- */

export default function App() {
  const [form, setForm] = useState(cargarMarca);
  const [errores, setErrores] = useState({});
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [apiError, setApiError] = useState("");
  const [videos, setVideos] = useState([]);
  const [online, setOnline] = useState(null);
  const [activeJob, setActiveJob] = useState(null); // job que se está sondeando
  const [lastJob, setLastJob] = useState(null); // último job lanzado (para la vista previa)
  const [step, setStep] = useState(0);

  const loading = status === "loading";
  const lastVideo = videos.find((v) => v.id === lastJob) ?? null;

  // Carga inicial del historial
  useEffect(() => {
    listarVideos()
      .then((lista) => {
        setVideos(lista);
        setOnline(true);
      })
      .catch(() => setOnline(false));
  }, []);

  // Recuerda la identidad de marca entre visitas
  useEffect(() => {
    try {
      const { negocio, nicho, tono } = form;
      localStorage.setItem(BRAND_KEY, JSON.stringify({ negocio, nicho, tono }));
    } catch {
      /* almacenamiento no disponible */
    }
  }, [form.negocio, form.nicho, form.tono]); // eslint-disable-line react-hooks/exhaustive-deps

  // Animación de pasos mientras se genera
  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => setStep((s) => Math.min(s + 1, PASOS.length - 1)), STEP_MS);
    return () => clearInterval(id);
  }, [loading]);

  // Sondeo del estado del video hasta que termine
  useEffect(() => {
    if (!activeJob) return;
    let cancelado = false;
    const inicio = Date.now();

    const consultar = async () => {
      try {
        const lista = await listarVideos();
        if (cancelado) return;
        setVideos(lista);
        setOnline(true);
        const job = lista.find((v) => v.id === activeJob);
        if (job && job.estado !== "procesando") {
          setActiveJob(null);
          if (job.estado === "listo") {
            setStatus("done");
          } else {
            setApiError(job.error || "El motor no pudo completar el video.");
            setStatus("error");
          }
          return;
        }
      } catch {
        if (!cancelado) setOnline(false);
      }
      if (!cancelado && Date.now() - inicio > POLL_TIMEOUT_MS) {
        setActiveJob(null);
        setApiError("El video está tardando más de lo normal. Revisa “Últimos videos” en unos minutos.");
        setStatus("error");
      }
    };

    const id = setInterval(consultar, POLL_MS);
    return () => {
      cancelado = true;
      clearInterval(id);
    };
  }, [activeJob]);

  const actualizar = (campo) => (e) => {
    const valor = e.target.value;
    setForm((f) => ({ ...f, [campo]: valor }));
    setErrores((prev) => ({ ...prev, [campo]: undefined }));
    if (status === "done" || status === "error") {
      setStatus("idle");
      setApiError("");
    }
  };

  const agregarEjemplo = (texto) => {
    setForm((f) => {
      const actual = f.tema.trim();
      if (actual.toLowerCase().includes(texto.toLowerCase())) return f;
      return { ...f, tema: actual ? `${actual}, ${texto}` : texto };
    });
    setErrores((prev) => ({ ...prev, tema: undefined }));
  };

  const enviar = async (e) => {
    e.preventDefault();
    if (loading) return;

    const errs = validar(form);
    setErrores(errs);
    if (Object.keys(errs).length > 0) return;

    setApiError("");
    setStep(0);
    setStatus("loading");
    try {
      const res = await generarVideo({
        negocio: form.negocio.trim(),
        nicho: form.nicho,
        tono: form.tono,
        tema: form.tema.trim(),
      });
      setLastJob(res.job_id);
      setVideos((prev) => [res.video, ...prev.filter((v) => v.id !== res.video.id)]);
      setActiveJob(res.job_id);
    } catch (err) {
      setApiError(err.message || "Ocurrió un error inesperado.");
      setStatus("error");
    }
  };

  return (
    <div className="pb-16">
      <Header online={online} />

      <main className="mx-auto mt-8 grid w-full max-w-6xl gap-6 px-5 sm:px-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <section className="glass rounded-2xl p-5 sm:p-7" aria-labelledby="config-titulo">
            <div className="mb-6">
              <h1 id="config-titulo" className="font-display text-2xl font-bold tracking-tight text-white">
                Crea tu próximo video viral
              </h1>
              <p className="mt-1.5 text-sm text-slate-400">
                Define tu marca, dinos de qué quieres hablar y nosotros nos encargamos del resto.
              </p>
            </div>

            <form onSubmit={enviar} noValidate className="space-y-6">
              <div className="grid gap-5 sm:grid-cols-2">
                <Field id="negocio" label="Nombre del negocio" error={errores.negocio}>
                  <input
                    id="negocio"
                    className="input"
                    value={form.negocio}
                    onChange={actualizar("negocio")}
                    placeholder="Ej. Barbería El Patrón"
                    maxLength={80}
                    autoComplete="organization"
                    aria-invalid={Boolean(errores.negocio)}
                    aria-describedby={errores.negocio ? "negocio-error" : undefined}
                    disabled={loading}
                  />
                </Field>

                <Field id="nicho" label="Nicho">
                  <select
                    id="nicho"
                    className="input appearance-none"
                    value={form.nicho}
                    onChange={actualizar("nicho")}
                    disabled={loading}
                  >
                    {NICHOS.map((n) => (
                      <option key={n} value={n} className="bg-ink-900">
                        {n}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <Field id="tono" label="Tono del contenido">
                <div id="tono" role="radiogroup" aria-label="Tono del contenido" className="flex flex-wrap gap-2">
                  {TONOS.map((t) => {
                    const activo = form.tono === t;
                    return (
                      <button
                        key={t}
                        type="button"
                        role="radio"
                        aria-checked={activo}
                        disabled={loading}
                        onClick={() => setForm((f) => ({ ...f, tono: t }))}
                        className={`rounded-full border px-4 py-2 text-sm transition disabled:opacity-60 ${
                          activo
                            ? "border-neon-violet/60 bg-neon-violet/15 text-white shadow-[0_0_20px_-6px_rgba(139,92,246,0.8)]"
                            : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200"
                        }`}
                      >
                        {t}
                      </button>
                    );
                  })}
                </div>
              </Field>

              <Field
                id="tema"
                label="Temas personalizados"
                hint="Separa varios con comas"
                error={errores.tema}
              >
                <textarea
                  id="tema"
                  className="input min-h-28 resize-y"
                  value={form.tema}
                  onChange={actualizar("tema")}
                  placeholder="Ej. Corte de pelo degradado, Chocolate belga…"
                  maxLength={300}
                  aria-invalid={Boolean(errores.tema)}
                  aria-describedby={errores.tema ? "tema-error" : undefined}
                  disabled={loading}
                />
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-slate-600">Ideas:</span>
                  {EJEMPLOS.map((ej) => (
                    <button
                      key={ej}
                      type="button"
                      onClick={() => agregarEjemplo(ej)}
                      disabled={loading}
                      className="rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-slate-400 transition hover:border-neon-cyan/40 hover:text-neon-cyan disabled:opacity-50"
                    >
                      + {ej}
                    </button>
                  ))}
                </div>
              </Field>

              {apiError && (
                <div
                  role="alert"
                  className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200"
                >
                  {apiError}
                </div>
              )}
              {status === "done" && (
                <div
                  role="status"
                  className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200"
                >
                  ¡Tu video está listo! Búscalo en “Últimos videos” o en tu canal de Telegram.
                </div>
              )}

              <div className="flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-slate-600">Tarda aproximadamente 1–3 minutos.</p>
                <button type="submit" className="btn-primary" disabled={loading}>
                  {loading ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      Generando…
                    </>
                  ) : (
                    <>
                      <IconSpark />
                      Generar video ahora
                    </>
                  )}
                </button>
              </div>
            </form>
          </section>

          <VideoList videos={videos} />
        </div>

        {/* Panel lateral */}
        <aside className="lg:sticky lg:top-6 lg:self-start" aria-label="Vista previa del video">
          <div className="glass grid-bg rounded-2xl p-6">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-display text-base font-semibold text-white">Previsualización</h2>
              <span className="rounded-md bg-white/5 px-2 py-0.5 text-[11px] text-slate-400">9:16</span>
            </div>
            <PhonePreview status={status} form={form} step={step} video={lastVideo} />
          </div>
        </aside>
      </main>
    </div>
  );
}
