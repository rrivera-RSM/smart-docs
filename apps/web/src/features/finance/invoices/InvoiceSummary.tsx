import type { InvoiceAnalysis } from "@/src/features/finance/api/client";

const currency = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
});

type Props = {
  analysis: InvoiceAnalysis;
};

export function InvoiceSummary({ analysis }: Props) {
  const reconciliation = analysis.reconciliation;

  return (
    <div className="invoice-summary">
      <article>
        <span>Proveedor</span>
        <strong>{analysis.provider}</strong>
        <small>{analysis.invoice_number}</small>
      </article>
      <article>
        <span>Fecha</span>
        <strong>{analysis.invoice_date}</strong>
        <small>{analysis.customer_name}</small>
      </article>
      <article>
        <span>Base imponible</span>
        <strong>{currency.format(analysis.taxable_base)}</strong>
        <small>{analysis.lines.length} líneas extraídas</small>
      </article>
      <article
        className={reconciliation.matches ? "summary-ok" : "summary-warning"}
      >
        <span>Conciliación</span>
        <strong>{reconciliation.matches ? "Correcta" : "Revisar"}</strong>
        <small>
          Diferencia {reconciliation.percentage_difference.toFixed(3)} %
        </small>
      </article>
    </div>
  );
}

