import type { Metadata } from "next";
import { headers } from "next/headers";
import type { PropsWithChildren } from "react";

import { AppShell } from "@/src/components/AppShell";

import "@/src/styles.css";
import "./people-analytics.css";

export async function generateMetadata(): Promise<Metadata> {
  const incomingHeaders = await headers();
  const forwardedHost = incomingHeaders.get("x-forwarded-host");
  const host = forwardedHost ?? incomingHeaders.get("host") ?? "127.0.0.1:3000";
  const protocol =
    incomingHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") || host.startsWith("127.0.0.1")
      ? "http"
      : "https");
  const metadataBase = new URL(
    process.env.NEXT_PUBLIC_APP_URL ?? `${protocol}://${host}`,
  );

  return {
    metadataBase,
    title: {
      default: "SmartDocs | RSM",
      template: "%s | SmartDocs",
    },
    description:
      "Espacio interno de RSM para generar y anonimizar documentos con revisión humana.",
    openGraph: {
      type: "website",
      locale: "es_ES",
      title: "SmartDocs",
      description: "Genera documentos. Protege datos.",
      images: [
        {
          url: "/og.png",
          width: 1729,
          height: 910,
          alt: "SmartDocs — Genera documentos. Protege datos.",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "SmartDocs",
      description: "Genera documentos. Protege datos.",
      images: ["/og.png"],
    },
  };
}

export default function RootLayout({ children }: PropsWithChildren) {
  return (
    <html lang="es" data-light-preset="slate-mist">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
