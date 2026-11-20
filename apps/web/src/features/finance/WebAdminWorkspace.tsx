"use client";

import {
  AlertTriangle,
  CheckCircle2,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  ShieldX,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getAccessOverview,
  type AccessOverview,
} from "@/src/features/finance/api/client";
import { getErrorMessage } from "@/src/features/finance/utils/errors";

const dateTime = new Intl.DateTimeFormat("es-ES", {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTime.format(date);
}

export function WebAdminWorkspace() {
  const [overview, setOverview] = useState<AccessOverview | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setOverview(await getAccessOverview());
    } catch (caught) {
      setError(
        getErrorMessage(
          caught,
          "No se ha podido cargar la información de acceso.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const users = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return overview?.users ?? [];
    return (overview?.users ?? []).filter((user) =>
      `${user.name} ${user.email}`.toLowerCase().includes(normalized),
    );
  }, [overview, query]);

  return (
    <section className="workspace-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">WebAdmin · Accesos</span>
          <h1>Acceso corporativo, sin listas paralelas.</h1>
          <p>
            Entra ID valida la identidad. Cualquier cuenta autenticada del
            tenant corporativo puede utilizar Imputación de gastos en SmartDocs.
          </p>
        </div>
        <span className="pilot-badge">Política tenant-only</span>
      </div>

      {error && (
        <div className="message message--error">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      <div className="access-policy-grid">
        <article className="panel access-policy-card access-policy-card--allowed">
          <span><ShieldCheck size={21} /></span>
          <div>
            <small>Quién puede acceder</small>
            <strong>Cuentas del tenant</strong>
            <p>{overview?.policy.allowed ?? "Identidades corporativas autenticadas."}</p>
          </div>
        </article>
        <article className="panel access-policy-card access-policy-card--denied">
          <span><ShieldX size={21} /></span>
          <div>
            <small>Quién queda fuera</small>
            <strong>Identidades no válidas</strong>
            <p>{overview?.policy.denied ?? "Sin sesión válida o fuera del tenant."}</p>
          </div>
        </article>
        <article className="panel access-policy-card">
          <span><Users size={21} /></span>
          <div>
            <small>Filtrado adicional</small>
            <strong>Ninguno</strong>
            <p>No hay allowlist, denylist ni roles de acceso propios.</p>
          </div>
        </article>
      </div>

      <article className="panel access-directory">
        <div className="access-directory__heading">
          <div className="panel-heading">
            <span className="panel-heading__icon"><Users size={21} /></span>
            <div>
              <h2>Usuarios observados</h2>
              <p>
                Personas que ya han accedido a Imputación de gastos. No es
                el directorio completo de Microsoft Entra ID.
              </p>
            </div>
          </div>
          <div className="access-directory__actions">
            <label className="access-search">
              <Search size={16} aria-hidden="true" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar por nombre o correo"
                aria-label="Buscar usuarios"
              />
            </label>
            <button
              type="button"
              className="icon-button access-refresh"
              onClick={() => void refresh()}
              disabled={busy}
              aria-label="Actualizar usuarios"
              title="Actualizar"
            >
              {busy ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />}
            </button>
          </div>
        </div>

        {busy && !overview ? (
          <div className="access-empty" role="status">
            <LoaderCircle className="spin" size={25} />
            <strong>Cargando información de acceso…</strong>
          </div>
        ) : !overview ? null : !overview.policy.auth_enabled ? (
          <div className="access-empty">
            <ShieldCheck size={25} />
            <strong>Entra ID todavía no está activo</strong>
            <p>El registro comenzará a completarse cuando se habilite el login corporativo.</p>
          </div>
        ) : users.length === 0 ? (
          <div className="access-empty">
            <Users size={25} />
            <strong>No hay usuarios observados</strong>
            <p>{query ? "No hay coincidencias para esta búsqueda." : "Aún no se ha registrado ningún acceso."}</p>
          </div>
        ) : (
          <div className="access-table-scroll">
            <table className="access-table">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Correo corporativo</th>
                  <th>Primer acceso</th>
                  <th>Último acceso</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.email}>
                    <td><strong>{user.name || "Sin nombre disponible"}</strong></td>
                    <td>{user.email}</td>
                    <td>{formatDate(user.first_seen_at)}</td>
                    <td>{formatDate(user.last_seen_at)}</td>
                    <td>
                      <span className="access-status">
                        <CheckCircle2 size={14} />Permitido por tenant
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>
    </section>
  );
}

