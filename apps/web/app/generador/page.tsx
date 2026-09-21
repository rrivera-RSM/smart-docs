import type { Metadata } from "next";

import { GeneratorPage } from "@/src/features/GeneratorPage";

export const metadata: Metadata = {
  title: "Generador de documentos",
};

export default function Page() {
  return <GeneratorPage />;
}
