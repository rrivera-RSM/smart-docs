import {
  AlertTriangle,
  Check,
  Download,
  RotateCcw,
} from "lucide-react";

import type {
  InvoiceAnalysis,
  InvoiceLine,
  InvoiceLineUpdate,
  LineStatus,
} from "@/src/features/finance/api/client";

const STATUS_LABELS: Record<LineStatus, string> = {
  proposed: "Propuesta",
  accepted: "Aceptada",
  pending: "Pendiente",
};

type Props = {
  analysis: InvoiceAnalysis;
  acceptedCount: number;
  pendingCount: number;
  busy: boolean;
  onReset: () => void;
  onAcceptAll: () => void;
  onStartExport: () => void;
  onUpdateLine: (lineId: string, changes: InvoiceLineUpdate) => void;
  onPersistLine: (
    line: InvoiceLine,
    changes?: InvoiceLineUpdate,
  ) => void | Promise<void>;
};

export function InvoiceReview({
  analysis,
  acceptedCount,
  pendingCount,
  busy,
  onReset,
  onAcceptAll,
  onStartExport,
  onUpdateLine,
  onPersistLine,
}: Props) {
  return (
    <>
      <article className="panel review-panel">
        <div className="review-toolbar">
          <div>
            <span className="eyebrow">Moderación</span>
            <h2>Detalle por usuario y servicio</h2>
            <p>
              Edita cualquier celda y decide qué líneas llegarán al Excel.
            </p>
          </div>
          <div className="toolbar-actions">
            <button
              className="button button--secondary"
              type="button"
              onClick={onReset}
            >
              <RotateCcw size={16} />
              Nueva factura
            </button>
            <button
              className="button button--success"
              type="button"
              onClick={onAcceptAll}
              disabled={busy}
            >
              <Check size={16} />
              Aceptar todas
            </button>
          </div>
        </div>

        <div className="grid-scroll">
          <table className="review-grid">
            <thead>
              <tr>
                <th>Estado</th>
                <th>Usuario</th>
                <th>Ref. proyecto</th>
                <th>Servicio</th>
                <th>Cantidad</th>
                <th>Precio unit.</th>
                <th>Importe</th>
                <th>Confianza</th>
                <th>Comentarios</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {analysis.lines.map((line) => (
                <tr key={line.id} className={`row-${line.status}`}>
                  <td>
                    <span className={`status status--${line.status}`}>
                      {STATUS_LABELS[line.status]}
                    </span>
                  </td>
                  <td>
                    <input
                      aria-label={`Usuario de ${line.service}`}
                      value={line.user}
                      onChange={(event) =>
                        onUpdateLine(line.id, { user: event.target.value })
                      }
                      onBlur={() => void onPersistLine(line)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Referencia de proyecto de ${line.service}`}
                      value={line.project_reference}
                      placeholder="Sin referencia"
                      onChange={(event) =>
                        onUpdateLine(line.id, {
                          project_reference: event.target.value,
                        })
                      }
                      onBlur={() => void onPersistLine(line)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label="Servicio"
                      value={line.service}
                      onChange={(event) =>
                        onUpdateLine(line.id, { service: event.target.value })
                      }
                      onBlur={() => void onPersistLine(line)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Cantidad de ${line.service}`}
                      type="number"
                      step="0.01"
                      value={line.quantity}
                      onChange={(event) =>
                        onUpdateLine(line.id, {
                          quantity: Number(event.target.value),
                        })
                      }
                      onBlur={() => void onPersistLine(line)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Precio unitario de ${line.service}`}
                      type="number"
                      step="0.0001"
                      value={line.unit_price}
                      onChange={(event) =>
                        onUpdateLine(line.id, {
                          unit_price: Number(event.target.value),
                        })
                      }
                      onBlur={() => void onPersistLine(line)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Importe de ${line.service}`}
                      type="number"
                      step="0.01"
                      value={line.amount}
                      onChange={(event) =>
                        onUpdateLine(line.id, {
                          amount: Number(event.target.value),
                        })
                      }
                      onBlur={() => void onPersistLine(line)}
                    />
                  </td>
                  <td>
                    <span className="confidence">
                      {Math.round(line.confidence * 100)} %
                    </span>
                  </td>
                  <td>
                    <input
                      aria-label={`Comentarios de ${line.service}`}
                      value={line.comment}
                      placeholder="Añadir nota"
                      onChange={(event) =>
                        onUpdateLine(line.id, { comment: event.target.value })
                      }
                      onBlur={() => void onPersistLine(line)}
                    />
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="accept-action"
                        type="button"
                        onClick={() =>
                          void onPersistLine(line, { status: "accepted" })
                        }
                        aria-label="Aceptar línea"
                      >
                        <Check size={16} />
                      </button>
                      <button
                        className="pending-action"
                        type="button"
                        onClick={() =>
                          void onPersistLine(line, { status: "pending" })
                        }
                        aria-label="Dejar pendiente"
                      >
                        <AlertTriangle size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <div className="export-bar">
        <div>
          <strong>
            {acceptedCount} aceptadas · {pendingCount} pendientes
          </strong>
          <span>Solo las líneas aceptadas aparecerán en el Excel final.</span>
        </div>
        <button
          className="button button--primary"
          type="button"
          disabled={busy || acceptedCount === 0}
          onClick={onStartExport}
        >
          <Download size={18} />
          Exportar Excel
        </button>
      </div>
    </>
  );
}

