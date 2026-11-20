"use client";

import {
  AlertTriangle,
  FileSearch,
  LoaderCircle,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  acceptAll,
  analyzeInvoice,
  exportInvoice,
  type InvoiceAnalysis,
  type InvoiceLine,
  type InvoiceLineUpdate,
  updateInvoiceLine,
} from "@/src/features/finance/api/client";
import { FileDropzone } from "@/src/features/finance/components/FileDropzone";
import { getErrorMessage } from "@/src/features/finance/utils/errors";

import { DiscardPendingDialog } from "./invoices/DiscardPendingDialog";
import { InvoiceProgress } from "./invoices/InvoiceProgress";
import { InvoiceReview } from "./invoices/InvoiceReview";
import { InvoiceSummary } from "./invoices/InvoiceSummary";

export function InvoiceWorkspace() {
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<InvoiceAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showDiscardWarning, setShowDiscardWarning] = useState(false);
  const [hasExported, setHasExported] = useState(false);

  const pendingCount = useMemo(
    () =>
      analysis?.lines.filter((line) => line.status !== "accepted").length ?? 0,
    [analysis],
  );
  const acceptedCount = (analysis?.lines.length ?? 0) - pendingCount;
  const currentStep = hasExported ? 3 : analysis ? 2 : 1;

  const reset = () => {
    setFile(null);
    setAnalysis(null);
    setError("");
    setShowDiscardWarning(false);
    setHasExported(false);
  };

  const runAnalysis = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      setAnalysis(await analyzeInvoice(file));
    } catch (caught) {
      setError(
        getErrorMessage(caught, "No se ha podido analizar la factura."),
      );
    } finally {
      setBusy(false);
    }
  };

  const updateLocalLine = (
    lineId: string,
    changes: InvoiceLineUpdate,
  ) => {
    setHasExported(false);
    setAnalysis((current) =>
      current
        ? {
            ...current,
            lines: current.lines.map((line) =>
              line.id === lineId ? { ...line, ...changes } : line,
            ),
          }
        : current,
    );
  };

  const persistLine = async (
    line: InvoiceLine,
    changes?: InvoiceLineUpdate,
  ) => {
    if (!analysis) return;
    setError("");
    setHasExported(false);

    try {
      setAnalysis(
        await updateInvoiceLine(
          analysis.job_id,
          line.id,
          changes ?? {
            user: line.user,
            project_reference: line.project_reference,
            service: line.service,
            quantity: line.quantity,
            unit_price: line.unit_price,
            amount: line.amount,
            comment: line.comment,
          },
        ),
      );
    } catch (caught) {
      setError(getErrorMessage(caught, "No se ha podido guardar la línea."));
    }
  };

  const acceptEveryLine = async () => {
    if (!analysis) return;
    setBusy(true);
    setError("");
    setHasExported(false);

    try {
      setAnalysis(await acceptAll(analysis.job_id));
    } catch (caught) {
      setError(
        getErrorMessage(caught, "No se han podido aceptar las líneas."),
      );
    } finally {
      setBusy(false);
    }
  };

  const download = async (confirmDiscardPending: boolean) => {
    if (!analysis) return;
    setBusy(true);
    setError("");

    try {
      const blob = await exportInvoice(
        analysis.job_id,
        confirmDiscardPending,
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${analysis.invoice_number}_validado.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);

      setShowDiscardWarning(false);
      setHasExported(true);
      if (confirmDiscardPending) {
        setAnalysis((current) =>
          current
            ? {
                ...current,
                lines: current.lines.filter(
                  (line) => line.status === "accepted",
                ),
              }
            : current,
        );
      }
    } catch (caught) {
      setError(
        getErrorMessage(caught, "No se ha podido exportar el Excel."),
      );
    } finally {
      setBusy(false);
    }
  };

  const startExport = () => {
    if (pendingCount > 0) {
      setShowDiscardWarning(true);
      return;
    }
    void download(false);
  };

  return (
    <section className="workspace-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Finanzas · Imputación asistida</span>
          <h1>Imputación de gastos</h1>
          <p>
            Extrae el detalle disponible, resuelve excepciones y exporta
            únicamente lo que Finanzas haya validado.
          </p>
        </div>
      </div>

      <InvoiceProgress currentStep={currentStep} />

      {error && (
        <div className="message message--error">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      {!analysis ? (
        <article className="panel panel--main upload-panel">
          <div className="panel-heading">
            <span className="panel-heading__icon">
              <FileSearch size={22} />
            </span>
            <div>
              <h2>Factura de proveedor</h2>
              <p>
                Sube una factura en PDF para extraer sus líneas y revisarlas.
              </p>
            </div>
          </div>
          <FileDropzone
            file={file}
            onFile={setFile}
            onClear={reset}
            disabled={busy}
          />
          <button
            className="button button--primary button--wide"
            type="button"
            disabled={!file || busy}
            onClick={() => void runAnalysis()}
          >
            {busy ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <FileSearch size={18} />
            )}
            {busy ? "Analizando factura…" : "Analizar factura"}
          </button>
        </article>
      ) : (
        <>
          <InvoiceSummary analysis={analysis} />
          <InvoiceReview
            analysis={analysis}
            acceptedCount={acceptedCount}
            pendingCount={pendingCount}
            busy={busy}
            onReset={reset}
            onAcceptAll={() => void acceptEveryLine()}
            onStartExport={startExport}
            onUpdateLine={updateLocalLine}
            onPersistLine={persistLine}
          />
        </>
      )}

      {showDiscardWarning && (
        <DiscardPendingDialog
          pendingCount={pendingCount}
          busy={busy}
          onCancel={() => setShowDiscardWarning(false)}
          onConfirm={() => void download(true)}
        />
      )}
    </section>
  );
}

