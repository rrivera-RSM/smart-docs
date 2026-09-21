export type DeploymentDocumentFormat = "docx" | "pdf" | "pptx";

function enabled(value: string | undefined): boolean {
  return ["1", "true", "yes", "on"].includes(value?.trim().toLowerCase() ?? "");
}

export const featureFlags = Object.freeze({
  pdf: enabled(process.env.NEXT_PUBLIC_SMARTDOCS_FEATURE_PDF),
  imageOcr: enabled(process.env.NEXT_PUBLIC_SMARTDOCS_FEATURE_IMAGE_OCR),
  webadmin: enabled(process.env.NEXT_PUBLIC_SMARTDOCS_FEATURE_WEBADMIN),
});

export const deploymentDocumentFormats: DeploymentDocumentFormat[] = [
  "docx",
  ...(featureFlags.pdf ? (["pdf"] as const) : []),
  "pptx",
];

export function extensionFor(format: string): string {
  return `.${format.toLowerCase()}`;
}

export function formatHint(formats: string[]): string {
  return formats.map((format) => format.toUpperCase()).join(" · ");
}
