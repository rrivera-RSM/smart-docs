import type { Metadata } from "next";
import { ProvidersWorkspace } from "@/src/features/finance/ProvidersWorkspace";

export const metadata: Metadata = { title: "Proveedores · Imputación de gastos" };

export default function Page() {
  return <ProvidersWorkspace />;
}
