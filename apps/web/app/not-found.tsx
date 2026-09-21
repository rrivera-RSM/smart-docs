import Link from "next/link";
import { ArrowLeft, FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <section className="not-found">
      <span className="not-found__icon">
        <FileQuestion aria-hidden="true" />
      </span>
      <p className="eyebrow">Página no encontrada</p>
      <h1>Este espacio no existe en SmartDocs</h1>
      <p>Vuelve al inicio para elegir uno de los flujos documentales.</p>
      <Link className="button button--primary" href="/">
        <ArrowLeft size={17} aria-hidden="true" />
        Volver al inicio
      </Link>
    </section>
  );
}
