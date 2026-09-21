"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  Eye,
  FileSearch,
  Info,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { apiUrl, smartDocsApi } from "../api/client";
import { FileDropzone } from "../components/FileDropzone";
import { Stepper } from "../components/Stepper";
import type {
  AnonymizationResult,
  AnonymizerAnalysis,
  Finding,
} from "../types";

const steps = [
  { label: "Documento", description: "Carga" },
  { label: "Detección", description: "Análisis" },
  { label: "Revisión", description: "Decisión humana" },
  { label: "Copia segura", description: "Descarga" },
];

type ReviewState = Record<
  string,
  {
    selected: boolean;
    replacement: string;
  }
>;

function findingLocation(location: string): string {
  if (location.includes(".header.")) return "Cabecera";
  if (location.includes(".footer.")) return "Pie de página";
  if (location.includes(".table[")) return "Tabla";
  return "Cuerpo";
}

function FindingRow({
  finding,
  state,
  onChange,
}: {
  finding: Finding;
  state: ReviewState[string];
  onChange: (next: ReviewState[string]) => void;
}) {
  return (
    <article className={"finding-row" + (state.selected ? " is-selected" : "")}>
      <label className="finding-row__check">
        <input
          type="checkbox"
          checked={state.selected}
          onChange={(event) =>
            onChange({ ...state, selected: event.target.checked })
          }
        />
        <span className="sr-only">Seleccionar {finding.label}</span>
      </label>

      <div className="finding-row__identity">
        <span className={"entity-badge entity-badge--" + finding.entity_type}>
          {finding.label}
        </span>
        <code>{finding.value}</code>
        <small>
          {findingLocation(finding.location)} ·{" "}
          {Math.round(finding.confidence * 100)}% confianza
        </small>
      </div>

      <div className="finding-row__context">
        <span>Contexto</span>
        <p>{finding.context}</p>
      </div>

      <label className="finding-row__replacement">
        <span>Sustituir por</span>
        <input
          value={state.replacement}
          disabled={!state.selected}
          maxLength={120}
          onChange={(event) =>
            onChange({ ...state, replacement: event.target.value })
          }
        />
      </label>
    </article>
  );
}

export function AnonymizerPage() {
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<AnonymizerAnalysis | null>(null);
  const [review, setReview] = useState<ReviewState>({});
  const [result, setResult] = useState<AnonymizationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCount = useMemo(
    () => Object.values(review).filter((item) => item.selected).length,
    [review],
  );

  const activeStep = result ? 4 : analysis ? 3 : file || busy ? 2 : 1;

  const reset = () => {
    setFile(null);
    setAnalysis(null);
    setReview({});
    setResult(null);
    setError(null);
  };

  const analyze = async (nextFile: File) => {
    setFile(nextFile);
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const payload = await smartDocsApi.analyzeForAnonymization(nextFile);
      setAnalysis(payload);
      setReview(
        Object.fromEntries(
          payload.findings.map((finding) => [
            finding.id,
            { selected: true, replacement: finding.replacement },
          ]),
        ),
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "No se pudo analizar.",
      );
    } finally {
      setBusy(false);
    }
  };

  const setAll = (selected: boolean) => {
    setReview((current) =>
      Object.fromEntries(
        Object.entries(current).map(([id, value]) => [
          id,
          { ...value, selected },
        ]),
      ),
    );
  };

  const apply = async () => {
    if (!analysis || selectedCount === 0) return;
    setBusy(true);
    setError(null);
    try {
      const decisions = analysis.findings
        .filter((finding) => review[finding.id]?.selected)
        .map((finding) => ({
          finding_id: finding.id,
          replacement: review[finding.id].replacement,
        }));
      setResult(
        await smartDocsApi.applyAnonymization(analysis.job_id, decisions),
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "No se pudo anonimizar.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="tool-page tool-page--wide">
      <Link className="back-link" href="/">
        <ArrowLeft size={16} aria-hidden="true" />
        Volver a SmartDocs
      </Link>

      <header className="tool-header">
        <div>
          <span className="eyebrow eyebrow--green">Data protection</span>
          <h1>Anonimizador de documentos</h1>
          <p>
            Detecta información estructurada, revisa cada coincidencia y genera
            una copia protegida del documento.
          </p>
        </div>
        <span className="tool-header__icon tool-header__icon--green">
          <ShieldCheck size={28} aria-hidden="true" />
        </span>
      </header>

      <Stepper steps={steps} active={activeStep} />

      {!analysis && (
        <div className="workspace-grid">
          <section className="workspace-card workspace-card--main">
            <div className="card-heading">
              <span className="card-heading__number">01</span>
              <div>
                <h2>Carga el documento original</h2>
                <p>Trabajaremos siempre sobre una copia del archivo.</p>
              </div>
            </div>
            <FileDropzone
              file={file}
              onFile={analyze}
              onClear={reset}
              disabled={busy}
            />
            {busy && (
              <div className="loading-state" role="status">
                <LoaderCircle className="spin" size={22} aria-hidden="true" />
                Buscando información sensible…
              </div>
            )}
            {error && (
              <div className="message message--error" role="alert">
                <AlertTriangle size={18} aria-hidden="true" />
                <span>{error}</span>
              </div>
            )}
          </section>

          <aside className="workspace-sidebar">
            <section className="workspace-card">
              <div className="sidebar-heading">
                <h2>Qué detectamos</h2>
              </div>
              <div className="detection-list">
                {["DNI y NIE", "IBAN español", "Correo electrónico", "Teléfono"].map(
                  (item) => (
                    <span key={item}>
                      <CheckCircle2 size={15} aria-hidden="true" />
                      {item}
                    </span>
                  ),
                )}
              </div>
              <div className="privacy-note">
                <Info size={17} aria-hidden="true" />
                <p>
                  Ningún cambio se aplica hasta que revises y confirmes los
                  hallazgos.
                </p>
              </div>
            </section>
          </aside>
        </div>
      )}

      {analysis && (
        <div className="review-workspace">
          <section className="review-summary">
            <div>
              <span className="review-summary__icon">
                <FileSearch size={22} aria-hidden="true" />
              </span>
              <div>
                <strong>{analysis.filename}</strong>
                <span>
                  {analysis.findings.length}{" "}
                  {analysis.findings.length === 1
                    ? "hallazgo detectado"
                    : "hallazgos detectados"}
                </span>
              </div>
            </div>
            <div className="summary-chips">
              {Object.entries(analysis.summary).map(([entity, count]) => (
                <span key={entity}>
                  {entity.replace("ES_", "")} <strong>{count}</strong>
                </span>
              ))}
            </div>
            <button className="button button--ghost" onClick={reset}>
              <RefreshCw size={16} aria-hidden="true" />
              Cambiar documento
            </button>
          </section>

          {analysis.findings.length === 0 ? (
            <section className="empty-result workspace-card">
              <span>
                <CheckCircle2 size={25} aria-hidden="true" />
              </span>
              <h2>No hemos encontrado coincidencias</h2>
              <p>
                El documento no contiene ninguno de los patrones estructurados
                incluidos en este MVP.
              </p>
              <button className="button button--secondary" onClick={reset}>
                Analizar otro documento
              </button>
            </section>
          ) : (
            <>
              <section className="review-toolbar">
                <div>
                  <Eye size={18} aria-hidden="true" />
                  <span>
                    <strong>{selectedCount}</strong> de{" "}
                    {analysis.findings.length} seleccionados
                  </span>
                </div>
                <div>
                  <button type="button" onClick={() => setAll(true)}>
                    Seleccionar todos
                  </button>
                  <button type="button" onClick={() => setAll(false)}>
                    Limpiar selección
                  </button>
                </div>
              </section>

              <section className="findings-list" aria-label="Hallazgos">
                {analysis.findings.map((finding) => (
                  <FindingRow
                    key={finding.id}
                    finding={finding}
                    state={review[finding.id]}
                    onChange={(next) =>
                      setReview((current) => ({
                        ...current,
                        [finding.id]: next,
                      }))
                    }
                  />
                ))}
              </section>

              {error && (
                <div className="message message--error" role="alert">
                  <AlertTriangle size={18} aria-hidden="true" />
                  <span>{error}</span>
                </div>
              )}

              <section className="review-actionbar">
                <div>
                  <strong>Revisión humana</strong>
                  <span>
                    Solo se sustituirán los {selectedCount} hallazgos
                    seleccionados.
                  </span>
                </div>
                <button
                  className="button button--success"
                  disabled={selectedCount === 0 || busy}
                  onClick={apply}
                >
                  {busy ? (
                    <LoaderCircle className="spin" size={17} aria-hidden="true" />
                  ) : (
                    <ShieldCheck size={17} aria-hidden="true" />
                  )}
                  Generar copia anonimizada
                </button>
              </section>
            </>
          )}

          {result && (
            <section className="completion-panel">
              <span className="completion-panel__icon">
                <CheckCircle2 size={27} aria-hidden="true" />
              </span>
              <div>
                <span className="eyebrow eyebrow--green">Proceso completado</span>
                <h2>La copia anonimizada está lista</h2>
                <p>
                  Se han aplicado {result.applied_count} sustituciones.
                  {result.remaining_count > 0
                    ? " Quedan " +
                      result.remaining_count +
                      " coincidencias no seleccionadas."
                    : " El reanálisis no ha encontrado coincidencias restantes."}
                </p>
              </div>
              <a
                className="button button--success"
                href={apiUrl(result.download_url)}
                download
              >
                <Download size={17} aria-hidden="true" />
                Descargar {result.filename}
              </a>
            </section>
          )}

          <details className="limitations">
            <summary>Alcance y limitaciones del MVP</summary>
            <ul>
              {analysis.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </div>
  );
}
