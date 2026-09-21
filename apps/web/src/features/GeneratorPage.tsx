"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  LoaderCircle,
  RefreshCw,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";

import { apiUrl, smartDocsApi } from "../api/client";
import { FileDropzone } from "../components/FileDropzone";
import { Stepper } from "../components/Stepper";
import {
  deploymentDocumentFormats,
  extensionFor,
  formatHint,
} from "../config/featureFlags";
import type { GenerationResult, GeneratorAnalysis } from "../types";
import styles from "./generator/generator.module.css";

const steps = [
  { label: "Cargar plantilla", description: formatHint(deploymentDocumentFormats) },
  { label: "Completar contenido", description: "Variables" },
  { label: "Descargar", description: "Documento final" },
];
const acceptedExtensions = deploymentDocumentFormats.map(extensionFor);
const supportedFormats = formatHint(deploymentDocumentFormats);

function variableLabel(variable: string): string {
  const label = variable.replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function GeneratorPage() {
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<GeneratorAnalysis | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeStep = useMemo(() => {
    if (result) return 3;
    if (analysis?.issues.length === 0 && analysis.variables.length > 0) return 2;
    return 1;
  }, [analysis, result]);

  const reset = () => {
    setFile(null);
    setAnalysis(null);
    setValues({});
    setResult(null);
    setError(null);
  };

  const analyze = async (nextFile: File) => {
    setFile(nextFile);
    setBusy(true);
    setError(null);
    setAnalysis(null);
    setResult(null);
    try {
      const payload = await smartDocsApi.analyzeTemplate(nextFile);
      setAnalysis(payload);
      setValues(
        Object.fromEntries(payload.variables.map((variable) => [variable, ""])),
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo analizar la plantilla.",
      );
    } finally {
      setBusy(false);
    }
  };

  const repair = async () => {
    if (!analysis) return;
    setBusy(true);
    setError(null);
    try {
      const payload = await smartDocsApi.repairTemplate(analysis.job_id);
      setAnalysis(payload);
      setValues(
        Object.fromEntries(payload.variables.map((variable) => [variable, ""])),
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo reparar la plantilla.",
      );
    } finally {
      setBusy(false);
    }
  };

  const generate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!analysis) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await smartDocsApi.generateDocument(analysis.job_id, values));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo generar el documento.",
      );
    } finally {
      setBusy(false);
    }
  };

  const hasIssues = Boolean(analysis?.issues.length);
  const hasNoVariables = Boolean(
    analysis &&
      analysis.issues.length === 0 &&
      analysis.variables.length === 0,
  );
  const canComplete = Boolean(
    analysis &&
      analysis.issues.length === 0 &&
      analysis.variables.length > 0,
  );

  return (
    <div className={styles.page}>
      <Link className={styles.backLink} href="/">
        <ArrowLeft size={16} aria-hidden="true" />
        Volver a Inicio
      </Link>

      <header className={styles.hero}>
        <span className={styles.eyebrow}>Creación documental</span>
        <h1>Genera documentos desde una plantilla.</h1>
        <p>
          Sube una plantilla compatible ({supportedFormats}), completa sus campos y descarga
          una copia en el formato original.
        </p>
      </header>

      <Stepper steps={steps} active={activeStep} />

      {error && (
        <div className="message message--error" role="alert">
          <AlertTriangle size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {!result && !canComplete && (
        <section className={`${styles.surface} ${styles.uploadPanel}`}>
          <div className={styles.sectionHeading}>
            <span>01</span>
            <div>
              <h2>Carga tu plantilla</h2>
              <p>Utiliza variables simples como {"{{ cliente }}"}.</p>
            </div>
          </div>

          <FileDropzone
            file={file}
            onFile={analyze}
            onClear={reset}
            disabled={busy}
            title={`Arrastra una plantilla ${supportedFormats}`}
            acceptedExtensions={acceptedExtensions}
            formatHint={supportedFormats}
          />

          {busy && (
            <div className={styles.processing} role="status">
              <LoaderCircle
                className={styles.spin}
                size={20}
                aria-hidden="true"
              />
              Analizando la plantilla…
            </div>
          )}

          {hasIssues && !busy && analysis && (
            <div className={styles.validationPanel}>
              <div className="message message--warning">
                <AlertTriangle size={19} aria-hidden="true" />
                <div>
                  <strong>
                    {analysis.issues.length}{" "}
                    {analysis.issues.length === 1
                      ? "marcador necesita revisión"
                      : "marcadores necesitan revisión"}
                  </strong>
                  <span>
                    Word ha dividido estos campos. Puedes repararlos antes de
                    continuar.
                  </span>
                </div>
              </div>

              <div className={styles.issueList}>
                {analysis.issues.map((issue) => (
                  <details key={issue.location + issue.variable}>
                    <summary>
                      {"{{ " + issue.variable + " }}"} · {issue.location}
                    </summary>
                    <p>{issue.paragraph_preview}</p>
                  </details>
                ))}
              </div>

              <div className={styles.actions}>
                <button className="button button--primary" onClick={repair}>
                  <WandSparkles size={17} aria-hidden="true" />
                  Reparar automáticamente
                </button>
                <button className="button button--ghost" onClick={reset}>
                  <RefreshCw size={16} aria-hidden="true" />
                  Cambiar plantilla
                </button>
              </div>
            </div>
          )}

          {hasNoVariables && !busy && (
            <div className={styles.emptyVariables}>
              <div className="message message--warning">
                <AlertTriangle size={18} aria-hidden="true" />
                <span>
                  No hemos encontrado variables con el formato{" "}
                  {"{{ variable }}"}.
                </span>
              </div>
              <button className="button button--ghost" onClick={reset}>
                <RefreshCw size={16} aria-hidden="true" />
                Elegir otra plantilla
              </button>
            </div>
          )}
        </section>
      )}

      {!result && canComplete && analysis && (
        <div className={styles.contentFlow}>
          <div className={styles.summaryBar}>
            <div>
              <FileText size={20} aria-hidden="true" />
              <div>
                <strong>{file?.name ?? analysis.filename}</strong>
                <span>Plantilla preparada</span>
              </div>
            </div>
            <div className={styles.summaryMetric}>
              <strong>{analysis.variables.length}</strong>
              <span>
                {analysis.variables.length === 1 ? "campo" : "campos"}
              </span>
            </div>
            <button type="button" onClick={reset}>
              <RefreshCw size={15} aria-hidden="true" />
              Cambiar plantilla
            </button>
          </div>

          <section className={styles.surface}>
            <div className={styles.sectionHeading}>
              <span>02</span>
              <div>
                <h2>Completa el contenido</h2>
                <p>Hemos creado estos campos a partir de tu plantilla.</p>
              </div>
            </div>

            <form className="variable-form" onSubmit={generate}>
              <div className="form-grid">
                {analysis.variables.map((variable) => (
                  <label key={variable} className="field">
                    <span>{variableLabel(variable)}</span>
                    <input
                      value={values[variable] ?? ""}
                      onChange={(event) =>
                        setValues((current) => ({
                          ...current,
                          [variable]: event.target.value,
                        }))
                      }
                      placeholder={"{{ " + variable + " }}"}
                    />
                  </label>
                ))}
              </div>
              <button
                className="button button--primary button--wide"
                disabled={busy}
                type="submit"
              >
                {busy ? (
                  <LoaderCircle
                    className={styles.spin}
                    size={17}
                    aria-hidden="true"
                  />
                ) : (
                  <WandSparkles size={17} aria-hidden="true" />
                )}
                {busy ? "Generando…" : "Generar documento"}
              </button>
            </form>
          </section>
        </div>
      )}

      {result && (
        <section className={`${styles.surface} ${styles.complete}`}>
          <span className={styles.completeIcon}>
            <CheckCircle2 size={29} aria-hidden="true" />
          </span>
          <div>
            <span className={styles.eyebrow}>Documento generado</span>
            <h2>Tu documento está listo.</h2>
            <p>{result.filename}</p>
          </div>
          <div className={styles.completeActions}>
            <a
              className="button button--success"
              href={apiUrl(result.download_url)}
              download
            >
              <Download size={17} aria-hidden="true" />
              Descargar documento
            </a>
            <button className="button button--ghost" onClick={reset}>
              <RefreshCw size={16} aria-hidden="true" />
              Usar otra plantilla
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
