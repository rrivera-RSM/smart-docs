import type { Metadata } from "next";
import type { PropsWithChildren } from "react";

import { FinanceNavigation } from "@/src/features/finance/FinanceNavigation";
import "@/src/features/finance/finance.css";

export const metadata: Metadata = {
  title: "Imputación de gastos",
  description: "Extrae, revisa e imputa líneas de facturas antes de exportarlas a Excel.",
};

export default function FinanceLayout({ children }: PropsWithChildren) {
  return (
    <div className="finance-workspace">
      <FinanceNavigation />
      {children}
    </div>
  );
}
