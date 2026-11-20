import type { Metadata } from "next";
import { WebAdminWorkspace } from "@/src/features/finance/WebAdminWorkspace";

export const metadata: Metadata = { title: "WebAdmin · Imputación de gastos" };

export default function Page() {
  return <WebAdminWorkspace />;
}
