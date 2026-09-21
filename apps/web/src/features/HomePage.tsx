import {
  FileText,
  ShieldCheck,
} from "lucide-react";

import { ToolCard } from "../components/ToolCard";

export function HomePage() {
  return (
    <div className="home-page">
      <header className="home-heading">
        <div>
          <h1>Proyectos documentales</h1>
          <p>Selecciona una opción para empezar.</p>
        </div>
      </header>

      <section className="tools-section" aria-labelledby="projects-title">
        <h2 id="projects-title" className="sr-only">
          Proyectos disponibles
        </h2>

        <div className="tool-grid">
          <ToolCard
            to="/generador"
            eyebrow="Creación documental"
            title="Generar documentos"
            description="Convierte una plantilla Word o PowerPoint en un formulario guiado y genera una copia lista para trabajar."
            action="Abrir proyecto"
            icon={FileText}
            tone="blue"
            features={[
              "Variables detectadas automáticamente",
              "Reparación de marcadores fragmentados",
              "Formato original preservado",
            ]}
          />
          <ToolCard
            to="/anonimizador"
            eyebrow="Protección de información"
            title="Anonimizar documentos"
            description="Detecta entidades, identificadores e importes; revisa cada grupo y genera una copia verificada."
            action="Abrir proyecto"
            icon={ShieldCheck}
            tone="green"
            features={[
              "Personas, empresas, ubicaciones e importes",
              "Revisión agrupada de detecciones",
              "Saneamiento y verificación residual",
            ]}
          />
        </div>
      </section>
    </div>
  );
}
