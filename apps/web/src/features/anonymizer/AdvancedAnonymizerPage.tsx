"use client";

import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  Download,
  FileSearch,
  FileText,
  Filter,
  LoaderCircle,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  deploymentDocumentFormats,
  extensionFor,
  formatHint,
} from "../../config/featureFlags";
import { anonymizerApi } from "./api";
import styles from "./anonymizer.module.css";
import { ReviewInspector, type GroupReview } from "./ReviewInspector";
import type { AnonymizerJob, Capability, ConfidenceBand } from "./contract";

const PROCESSING = new Set(["queued", "extracting", "detecting", "applying"]);
const STATUS_LABEL: Record<string, string> = {
  queued: "Preparando el documento",
  extracting: "Leyendo el documento",
  detecting: "Buscando información sensible",
  review_ready: "Listo para revisión",
  applying: "Creando la copia anonimizada",
  ready: "Documento listo",
  failed: "Proceso detenido",
};

const delay = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function hydrateReview(job: AnonymizerJob, current: GroupReview = {}): GroupReview {
  return Object.fromEntries(
    job.groups.map((group) => [
      group.id,
      current[group.id] ?? {
        selected: group.selected_by_default,
        replacement: group.replacement,
        expanded: false,
      },
    ]),
  );
}

async function pollJob(jobId: string, onUpdate: (job: AnonymizerJob) => void): Promise<AnonymizerJob> {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const job = await anonymizerApi.get(jobId);
    onUpdate(job);
    if (!PROCESSING.has(job.status)) return job;
    await delay(500);
  }
  throw new Error("El proceso está tardando más de lo esperado. La sesión sigue disponible durante 30 minutos.");
}

export function AdvancedAnonymizerPage() {
  const [capabilities, setCapabilities] = useState<Capability | null>(null);
  const [enabledCategories, setEnabledCategories] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [allowlist, setAllowlist] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [job, setJob] = useState<AnonymizerJob | null>(null);
  const [review, setReview] = useState<GroupReview>({});
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [band, setBand] = useState<ConfidenceBand | "all">("all");
  const [reviewConfirmed, setReviewConfirmed] = useState(false);
  const [removeUnsupported, setRemoveUnsupported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    anonymizerApi.capabilities()
      .then((payload) => {
        setCapabilities(payload);
        setEnabledCategories(payload.categories.filter((item) => item.enabled_by_default).map((item) => item.id));
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "No se pudo comprobar el motor local."));
  }, []);

  const currentStep = job?.status === "ready" ? 3 : job ? 2 : 1;
  const availableFormats = useMemo(
    () => (
      capabilities
        ? capabilities.formats.filter((format) => format.enabled).map((format) => format.id)
        : deploymentDocumentFormats
    ),
    [capabilities],
  );
  const acceptedExtensions = useMemo(
    () => availableFormats.map(extensionFor),
    [availableFormats],
  );
  const supportedFormats = formatHint(availableFormats);
  const blockingIssues = job?.coverage_issues.filter((issue) => issue.blocking) ?? [];
  const removableIssues = blockingIssues.filter((issue) => issue.removable);
  const hasHardBlock = blockingIssues.some((issue) => !issue.removable);
  const selectedOccurrences = useMemo(
    () => job?.groups.reduce((total, group) => total + (review[group.id]?.selected ? group.occurrence_count : 0), 0) ?? 0,
    [job, review],
  );
  const availableCategories = useMemo(
    () => Array.from(new Set(job?.groups.map((group) => group.entity_type) ?? [])),
    [job],
  );
  const visibleGroups = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("es");
    return (job?.groups ?? []).filter((group) =>
      (category === "all" || group.entity_type === category) &&
      (band === "all" || group.confidence_band === band) &&
      (!normalizedQuery || `${group.label} ${group.value}`.toLocaleLowerCase("es").includes(normalizedQuery)),
    );
  }, [job, query, category, band]);

  const selectFile = (candidate: File | undefined) => {
    if (!candidate) return;
    if (!acceptedExtensions.some((extension) => candidate.name.toLowerCase().endsWith(extension))) {
      setError(`Selecciona un documento compatible (${supportedFormats}).`);
      return;
    }
    if (candidate.size > 15 * 1024 * 1024) {
      setError("El documento supera el límite de 15 MB.");
      return;
    }
    setFile(candidate);
    setError(null);
  };

  const reset = async () => {
    const jobId = job?.job_id;
    setFile(null);
    setJob(null);
    setReview({});
    setReviewConfirmed(false);
    setRemoveUnsupported(false);
    setError(null);
    if (jobId) await anonymizerApi.remove(jobId).catch(() => undefined);
  };

  const analyze = async () => {
    if (!file || !capabilities?.model.ready) return;
    setBusy(true);
    setError(null);
    try {
      const created = await anonymizerApi.analyze(file, {
        profile: "maximum",
        enabled_categories: enabledCategories,
        allowlist: allowlist.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
      });
      setJob(created);
      const completed = await pollJob(created.job_id, setJob);
      if (completed.status === "failed") throw new Error(completed.error ?? "No se pudo analizar el documento.");
      setReview(hydrateReview(completed));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo analizar el documento.");
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!job || !reviewConfirmed || hasHardBlock || (removableIssues.length > 0 && !removeUnsupported)) return;
    setBusy(true);
    setError(null);
    try {
      const accepted = await anonymizerApi.apply(
        job.job_id,
        job.groups.map((group) => ({
          group_id: group.id,
          action: review[group.id]?.selected ? "replace" : "keep",
          replacement: review[group.id]?.selected ? review[group.id].replacement : undefined,
        })),
        removeUnsupported,
      );
      setJob(accepted);
      const completed = await pollJob(job.job_id, setJob);
      if (completed.status === "failed") throw new Error(completed.error ?? "La verificación residual ha fallado.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo generar la copia anonimizada.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.page}>
      <Link className={styles.backLink} href="/"><ArrowLeft size={16} /> Volver a Inicio</Link>

      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>Protección documental</span>
          <h1>Anonimiza documentos antes de compartirlos.</h1>
          <p>Sube un documento compatible ({supportedFormats}), revisa las detecciones y descarga una copia protegida.</p>
        </div>
      </header>
      <ol className={styles.steps} aria-label="Progreso">
        {["Cargar documento", "Revisar detecciones", "Descargar"].map((label, index) => {
          const step = index + 1;
          return (
            <li className={step < currentStep ? styles.stepDone : step === currentStep ? styles.stepActive : ""} key={label}>
              <span>{step < currentStep ? <Check size={14} /> : step}</span>{label}
            </li>
          );
        })}
      </ol>

      {error && <div className={styles.error} role="alert"><AlertTriangle size={18} /><span>{error}</span>{job?.status === "failed" && <button type="button" onClick={reset}><Trash2 size={15} /> Eliminar sesión</button>}</div>}
      {!job && (
        <section className={`${styles.surface} ${styles.uploadPanel}`}>
          <div className={styles.sectionHeading}>
            <span><FileSearch size={18} /></span>
            <div><h2>Documento a anonimizar</h2><p>Formatos disponibles: {supportedFormats}.</p></div>
          </div>

          <label
            className={`${styles.dropzone} ${dragActive ? styles.dragging : ""}`}
            onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragActive(false)}
            onDrop={(event) => { event.preventDefault(); setDragActive(false); selectFile(event.dataTransfer.files[0]); }}
          >
            <input type="file" accept={acceptedExtensions.join(",")} onChange={(event) => selectFile(event.target.files?.[0])} />
            {file ? <FileText size={28} /> : <UploadCloud size={30} />}
            <strong>{file?.name ?? `Arrastra un documento ${supportedFormats}`}</strong>
            <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · listo para analizar` : `${supportedFormats} · hasta 15 MB`}</span>
            {file && <button type="button" onClick={(event) => { event.preventDefault(); setFile(null); }} aria-label="Quitar archivo"><X size={16} /></button>}
          </label>

          <details className={styles.advancedSettings}>
            <summary>
              <Settings2 size={17} />
              <span><strong>Opciones de detección</strong><small>Configuración opcional · {enabledCategories.length} categorías activas</small></span>
            </summary>
            <div className={styles.advancedSettingsBody}>
              <div className={styles.categoryGrid}>
                {(capabilities?.categories ?? []).map((item) => (
                  <label key={item.id}>
                    <input type="checkbox" checked={enabledCategories.includes(item.id)} onChange={(event) => setEnabledCategories((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} />
                    <span>{item.label}</span>
                  </label>
                ))}
              </div>
              <label className={styles.allowlist}>
                <span>Texto que no debe anonimizarse <small>una expresión exacta por línea</small></span>
                <textarea value={allowlist} onChange={(event) => setAllowlist(event.target.value)} placeholder={"Ej.: RSM España\nProyecto Horizonte"} rows={3} />
              </label>
            </div>
          </details>

          {capabilities && !capabilities.model.ready && (
            <div className={styles.error}><AlertTriangle size={18} /><span>{capabilities.model.detail}</span></div>
          )}
          <button className={`${styles.primaryButton} ${styles.primaryButtonWide}`} type="button" onClick={analyze} disabled={!file || busy || !capabilities?.model.ready || enabledCategories.length === 0}>
            {busy ? <LoaderCircle className={styles.spin} size={18} /> : <FileSearch size={18} />}
            Analizar documento
          </button>
        </section>
      )}
      {job && job.status !== "review_ready" && job.status !== "ready" && (
        <section className={styles.processing}>
          <div className={styles.processingIcon}>{job.status === "failed" ? <AlertTriangle size={29} /> : <LoaderCircle className={styles.spin} size={29} />}</div>
          <h2>{STATUS_LABEL[job.status]}</h2>
          <p>{job.status === "applying" ? "Aplicando tus decisiones y comprobando el resultado." : "Esto puede tardar unos segundos."}</p>
          <div className={styles.progress}><span style={{ width: `${job.progress}%` }} /></div>
          <small>{job.progress}%</small>
        </section>
      )}

      {job && (job.status === "review_ready" || job.status === "ready") && (
        <div className={styles.reviewArea}>
          <section className={styles.summaryBar}>
            <div><FileSearch size={21} /><div><strong>{job.filename}</strong><span>{job.groups.length} grupos · {job.findings.length} apariciones</span></div></div>
            <div className={styles.summaryMetric}><strong>{selectedOccurrences}</strong><span>redacciones</span></div>
            <div className={styles.summaryMetric}><strong>{blockingIssues.length}</strong><span>bloqueos</span></div>
            <button type="button" onClick={reset}><RefreshCw size={15} /> Cambiar documento</button>
          </section>

          {job.status === "ready" && job.download_url ? (
            <section className={styles.complete}>
              <span><CheckCircle2 size={30} /></span>
              <div><span className={styles.eyebrow}>Verificación completada</span><h2>La copia anonimizada está lista</h2><p>{job.applied_count ?? 0} sustituciones aplicadas. El {job.document_format.toUpperCase()} se ha reabierto y validado antes de habilitar la descarga.</p></div>
              <a className={styles.downloadButton} href={anonymizerApi.downloadUrl(job.download_url)} download><Download size={18} /> Descargar copia</a>
            </section>
          ) : (
            <>
              <section className={styles.coveragePanel}>
                <div className={blockingIssues.length ? styles.coverageAlert : styles.coverageOk}>{blockingIssues.length ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}</div>
                <div><strong>{blockingIssues.length ? "Cobertura incompleta" : "Todo el contenido es inspeccionable"}</strong><p>{blockingIssues.length ? "Hay contenido que el motor no puede leer con seguridad." : "El contenido compatible se ha podido inspeccionar."}</p></div>
                {removableIssues.length > 0 && <label><input type="checkbox" checked={removeUnsupported} onChange={(event) => setRemoveUnsupported(event.target.checked)} /><span>Eliminar de la copia: {removableIssues.map((issue) => issue.label).join(", ")}</span></label>}
                {hasHardBlock && <span>No se puede generar una copia segura hasta retirar o convertir las páginas indicadas.</span>}
              </section>

              <section className={styles.findingsPanel}>
                <div className={styles.panelHeading}><div><span className={styles.kicker}>Revisión</span><h2>Revisar detecciones</h2></div><span>{visibleGroups.length} de {job.groups.length}</span></div>
                <div className={styles.filters}>
                  <label className={styles.search}><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar texto detectado" /></label>
                  <label><Filter size={14} /><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">Todas las categorías</option>{availableCategories.map((item) => <option key={item} value={item}>{job.groups.find((group) => group.entity_type === item)?.label ?? item}</option>)}</select></label>
                  <label><select value={band} onChange={(event) => setBand(event.target.value as ConfidenceBand | "all")}><option value="all">Toda confianza</option><option value="validated">Validado</option><option value="probable">Probable</option><option value="review">Revisar</option></select></label>
                </div>
                <div className={styles.bulkActions}><button type="button" onClick={() => setReview((current) => Object.fromEntries(Object.entries(current).map(([id, value]) => [id, { ...value, selected: true }])))}>Aprobar todas</button><button type="button" onClick={() => setReview((current) => Object.fromEntries(Object.entries(current).map(([id, value]) => [id, { ...value, selected: false }])))}>Omitir todas</button></div>
                <ReviewInspector groups={visibleGroups} findings={job.findings} review={review} onChange={(id, next) => setReview((current) => ({ ...current, [id]: next }))} />
              </section>

              <section className={styles.confirmationBar}>
                <label><input type="checkbox" checked={reviewConfirmed} onChange={(event) => setReviewConfirmed(event.target.checked)} /><span><strong>He revisado las detecciones</strong><small>Confirmo qué información se anonimizará.</small></span></label>
                <button type="button" className={styles.primaryButton} onClick={apply} disabled={busy || selectedOccurrences === 0 || !reviewConfirmed || hasHardBlock || (removableIssues.length > 0 && !removeUnsupported)}>{busy ? <LoaderCircle className={styles.spin} size={18} /> : <ShieldCheck size={18} />} Anonimizar y verificar</button>
              </section>
            </>
          )}
        </div>
      )}

    </div>
  );
}
