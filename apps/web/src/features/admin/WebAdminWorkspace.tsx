"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileText,
  LoaderCircle,
  RefreshCw,
  Server,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { loadAdminSnapshot, type AdminSnapshot } from "./api";
import styles from "./admin.module.css";

export function WebAdminWorkspace() {
  const [snapshot, setSnapshot] = useState<AdminSnapshot | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setSnapshot(await loadAdminSnapshot());
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se ha podido comprobar el entorno.",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const services = useMemo(
    () => [
      {
        id: "generator",
        name: "Generador de documentos",
        format: "DOCX",
        engine: "Plantillas y validación",
        ready: snapshot?.health.status === "ok",
      },
      {
        id: "anonymizer",
        name: "Anonimizador",
        format: "DOCX",
        engine: snapshot?.capabilities.model.provider ?? "NER español + reglas",
        ready: snapshot?.capabilities.model.ready ?? false,
      },
    ],
    [snapshot],
  );

  return (
    <section className={styles.page}>
      <header className={styles.heading}>
        <div>
          <span className={styles.eyebrow}>WebAdmin · Entorno</span>
          <h1>Configuración y estado de SmartDocs.</h1>
          <p>Información operativa del piloto, separada de las tareas documentales.</p>
        </div>
        <span className={styles.pilotBadge}>Piloto interno</span>
      </header>

      {error && (
        <div className={styles.error} role="alert">
          <AlertTriangle size={18} />
          <span>{error}</span>
          <button type="button" onClick={() => void refresh()}>Reintentar</button>
        </div>
      )}

      <div className={styles.policyGrid}>
        <article className={[styles.panel, styles.policyCard, styles.policyAllowed].join(" ")}>
          <span><ShieldCheck size={21} /></span>
          <div>
            <small>Acceso actual</small>
            <strong>Red interna controlada</strong>
            <p>El piloto se ejecuta en un entorno interno, sin cuentas propias de SmartDocs.</p>
          </div>
        </article>
        <article className={[styles.panel, styles.policyCard, styles.policyPending].join(" ")}>
          <span><ShieldX size={21} /></span>
          <div>
            <small>Autenticación corporativa</small>
            <strong>No configurada</strong>
            <p>La integración con Microsoft Entra ID queda pendiente antes de producción.</p>
          </div>
        </article>
        <article className={[styles.panel, styles.policyCard].join(" ")}>
          <span><Clock3 size={21} /></span>
          <div>
            <small>Retención documental</small>
            <strong>30 minutos</strong>
            <p>Los originales y resultados se eliminan al expirar la sesión local.</p>
          </div>
        </article>
      </div>

      <article className={[styles.panel, styles.directory].join(" ")}>
        <div className={styles.directoryHeading}>
          <div className={styles.panelHeading}>
            <span><Server size={21} /></span>
            <div>
              <h2>Servicios</h2>
              <p>Disponibilidad actual de los proyectos documentales.</p>
            </div>
          </div>
          <button
            type="button"
            className={styles.refreshButton}
            onClick={() => void refresh()}
            disabled={busy}
            aria-label="Actualizar estado"
            title="Actualizar"
          >
            {busy ? <LoaderCircle className={styles.spin} size={17} /> : <RefreshCw size={17} />}
          </button>
        </div>

        <div className={styles.tableScroll}>
          <table className={styles.serviceTable}>
            <thead>
              <tr><th>Proyecto</th><th>Formato</th><th>Motor</th><th>Estado</th></tr>
            </thead>
            <tbody>
              {services.map((service) => (
                <tr key={service.id}>
                  <td><span className={styles.serviceName}><FileText size={16} /><strong>{service.name}</strong></span></td>
                  <td>{service.format}</td>
                  <td>{service.engine}</td>
                  <td>
                    <span className={service.ready ? styles.statusReady : styles.statusPending}>
                      {service.ready ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                      {busy && !snapshot ? "Comprobando" : service.ready ? "Disponible" : "Requiere atención"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <aside className={styles.accessNote}>
        <AlertTriangle size={19} />
        <div>
          <strong>Control de usuarios pendiente</strong>
          <p>Esta versión no registra identidades ni accesos. La vista de usuarios observados se habilitará junto con Entra ID.</p>
        </div>
      </aside>
    </section>
  );
}