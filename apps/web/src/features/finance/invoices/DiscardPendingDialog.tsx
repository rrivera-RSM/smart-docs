import { AlertTriangle } from "lucide-react";

type Props = {
  pendingCount: number;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function DiscardPendingDialog({
  pendingCount,
  busy,
  onCancel,
  onConfirm,
}: Props) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="discard-title"
      >
        <span className="modal__icon">
          <AlertTriangle size={24} />
        </span>
        <h2 id="discard-title">Hay {pendingCount} líneas pendientes</h2>
        <p>
          Si continúas, estas líneas se eliminarán definitivamente y no
          aparecerán en el Excel. Esta acción no se puede deshacer.
        </p>
        <div className="modal__actions">
          <button
            className="button button--secondary"
            type="button"
            onClick={onCancel}
          >
            Volver a revisar
          </button>
          <button
            className="button button--danger"
            type="button"
            onClick={onConfirm}
            disabled={busy}
          >
            Eliminar pendientes y exportar
          </button>
        </div>
      </div>
    </div>
  );
}

