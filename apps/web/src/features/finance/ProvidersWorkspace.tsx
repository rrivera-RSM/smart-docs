"use client";

import {
  AlertTriangle,
  Braces,
  CheckCircle2,
  FileJson2,
  FileSearch,
  LoaderCircle,
  Plus,
  Save,
  Settings2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  getProviderProfile,
  listProviders,
  saveProviderProfile,
  testProviderProfile,
  type ProviderSummary,
  type ProviderTestResult,
} from "@/src/features/finance/api/client";
import { getErrorMessage } from "@/src/features/finance/utils/errors";

export function ProvidersWorkspace() {
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [profileText, setProfileText] = useState("");
  const [sample, setSample] = useState<File | null>(null);
  const [preview, setPreview] = useState<ProviderTestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    try {
      setProviders(await listProviders());
    } catch (caught) {
      setError(
        getErrorMessage(caught, "No se ha podido cargar el catálogo."),
      );
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const resetFeedback = () => {
    setMessage("");
    setError("");
  };

  const readProfileFile = async (file: File | null) => {
    if (!file) return;
    resetFeedback();
    setProfileText(await file.text());
    setPreview(null);
  };

  const loadTemplate = async () => {
    setBusy(true);
    resetFeedback();

    try {
      const profile = await getProviderProfile("lleidanet");
      setProfileText(
        JSON.stringify(
          {
            ...profile,
            id: "nuevo-proveedor",
            name: "Nuevo proveedor",
            description: "Perfil pendiente de configurar.",
          },
          null,
          2,
        ),
      );
      setPreview(null);
      setMessage(
        "Plantilla cargada. Cambia id, nombre, detección y patrones antes de probarla.",
      );
    } catch (caught) {
      setError(
        getErrorMessage(caught, "No se ha podido cargar la plantilla."),
      );
    } finally {
      setBusy(false);
    }
  };

  const runTest = async () => {
    if (!profileText || !sample) return;
    setBusy(true);
    resetFeedback();

    try {
      const result = await testProviderProfile(profileText, sample);
      setPreview(result);
      setMessage(
        result.detection_matches
          ? "La muestra encaja con el perfil. Ya puedes guardarlo."
          : "La extracción funciona, pero los términos de detección no reconocen esta muestra.",
      );
    } catch (caught) {
      setPreview(null);
      setError(
        getErrorMessage(caught, "El perfil no ha superado la prueba."),
      );
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    resetFeedback();

    try {
      const parsed = JSON.parse(profileText) as Record<string, unknown>;
      const saved = await saveProviderProfile(parsed);
      setMessage(
        `${saved.name} se ha añadido al catálogo sin desplegar código.`,
      );
      await refresh();
    } catch (caught) {
      setError(
        getErrorMessage(caught, "No se ha podido guardar el perfil."),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="workspace-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Administración · Proveedores</span>
          <h1>Integra formatos sin añadir código.</h1>
          <p>
            Carga reglas declarativas, compruébalas con una factura real y
            actívalas en el catálogo local.
          </p>
        </div>
        <span className="pilot-badge">Motor configurable</span>
      </div>

      {error && (
        <div className="message message--error">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}
      {message && (
        <div className="message message--success">
          <CheckCircle2 size={18} />
          {message}
        </div>
      )}

      <div className="provider-layout">
        <aside className="panel provider-catalog">
          <div className="panel-heading">
            <span className="panel-heading__icon">
              <Settings2 size={21} />
            </span>
            <div>
              <h2>Catálogo activo</h2>
              <p>{providers.length} perfiles disponibles</p>
            </div>
          </div>
          <div className="provider-list">
            {providers.map((provider) => (
              <article key={provider.id} className="provider-card">
                <div>
                  <strong>{provider.name}</strong>
                  <span>
                    {provider.mode === "grouped_detail"
                      ? "Detalle agrupado"
                      : "Tabla plana"}
                  </span>
                </div>
                <small>{provider.built_in ? "Base" : "Añadido"}</small>
                <p>
                  {provider.description ||
                    provider.detection_terms.join(" · ")}
                </p>
              </article>
            ))}
          </div>
        </aside>

        <article className="panel provider-onboarding">
          <div className="panel-heading provider-heading">
            <span className="panel-heading__icon">
              <Plus size={22} />
            </span>
            <div>
              <h2>Alta de proveedor</h2>
              <p>
                El perfil contiene únicamente configuración; nunca ejecuta
                código.
              </p>
            </div>
            <button
              className="button button--secondary"
              type="button"
              onClick={() => void loadTemplate()}
              disabled={busy}
            >
              <Braces size={16} />
              Cargar ejemplo
            </button>
          </div>

          <div className="provider-inputs">
            <label className="file-field">
              <span>
                <FileJson2 size={20} />
              </span>
              <div>
                <strong>1. Perfil JSON</strong>
                <small>Reglas de detección y extracción</small>
              </div>
              <input
                type="file"
                accept="application/json,.json"
                onChange={(event) =>
                  void readProfileFile(event.target.files?.[0] ?? null)
                }
              />
              <em>
                <Upload size={15} />
                Seleccionar
              </em>
            </label>

            <label className="file-field">
              <span>
                <FileSearch size={20} />
              </span>
              <div>
                <strong>2. Factura de muestra</strong>
                <small>
                  {sample?.name ?? "PDF digital del proveedor"}
                </small>
              </div>
              <input
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => {
                  setSample(event.target.files?.[0] ?? null);
                  setPreview(null);
                }}
              />
              <em>
                <Upload size={15} />
                Seleccionar
              </em>
            </label>
          </div>

          <label className="profile-editor">
            <span>
              <Braces size={16} />
              Configuración avanzada
            </span>
            <textarea
              value={profileText}
              onChange={(event) => {
                setProfileText(event.target.value);
                setPreview(null);
              }}
              placeholder="Carga un perfil JSON o parte de la plantilla base."
              spellCheck={false}
            />
          </label>

          <div className="provider-actions">
            <button
              className="button button--secondary"
              type="button"
              disabled={!profileText || !sample || busy}
              onClick={() => void runTest()}
            >
              {busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <FileSearch size={17} />
              )}
              Probar con la muestra
            </button>
            <button
              className="button button--primary"
              type="button"
              disabled={!preview?.detection_matches || busy}
              onClick={() => void save()}
            >
              <Save size={17} />
              Guardar y activar
            </button>
          </div>

          {preview && (
            <div className="provider-preview">
              <div>
                <span
                  className={
                    preview.detection_matches
                      ? "test-ok"
                      : "test-warning"
                  }
                >
                  {preview.detection_matches
                    ? "Detección correcta"
                    : "Revisar detección"}
                </span>
                <strong>
                  {preview.analysis.provider} ·{" "}
                  {preview.analysis.invoice_number}
                </strong>
              </div>
              <div>
                <span>Líneas</span>
                <strong>{preview.analysis.lines.length}</strong>
              </div>
              <div>
                <span>Base</span>
                <strong>
                  {preview.analysis.taxable_base.toFixed(2)} €
                </strong>
              </div>
              <div>
                <span>Conciliación</span>
                <strong>
                  {preview.analysis.reconciliation.matches
                    ? "Correcta"
                    : "Revisar"}
                </strong>
              </div>
            </div>
          )}

          <div className="privacy-note provider-note">
            <FileJson2 size={18} />
            <span>
              El alta cubre PDFs de texto con estructuras agrupadas o tablas
              planas. Un PDF escaneado seguirá necesitando OCR; un formato
              realmente irregular requerirá IA documental o una regla
              especializada.
            </span>
          </div>
        </article>
      </div>
    </section>
  );
}

