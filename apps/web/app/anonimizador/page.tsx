import type { Metadata } from "next";

import { AdvancedAnonymizerPage } from "@/src/features/anonymizer/AdvancedAnonymizerPage";

export const metadata: Metadata = {
  title: "Anonimizador de documentos",
};

export default function Page() {
  return <AdvancedAnonymizerPage />;
}
