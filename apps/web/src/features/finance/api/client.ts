import { getSession } from "next-auth/react";

import type {
  AccessOverview,
  InvoiceAnalysis,
  InvoiceLineUpdate,
  ProviderSummary,
  ProviderTestResult,
} from "./contracts";

export type {
  AccessOverview,
  InvoiceAnalysis,
  InvoiceLine,
  InvoiceLineUpdate,
  LineStatus,
  ObservedAccessUser,
  ProviderSummary,
  ProviderTestResult,
} from "./contracts";

const DEFAULT_ERROR = "No se ha podido completar la operación.";

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return payload.detail;
    if (typeof payload.detail?.message === "string") {
      return payload.detail.message;
    }
  } catch {
    // Some upstream errors have no JSON body; use the stable fallback below.
  }
  return DEFAULT_ERROR;
}

async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const response = await fetch(input, init);
  if (response.status !== 401) return response;

  // Refresh through the shared SmartDocs session. A 401 is rejected before
  // the operation executes, so retry it once after refreshing credentials.
  const session = await getSession();
  return session ? fetch(input, init) : response;
}

async function requestJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const response = await apiFetch(input, init);
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json() as Promise<T>;
}

async function requestBlob(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Blob> {
  const response = await apiFetch(input, init);
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.blob();
}

export function analyzeInvoice(file: File): Promise<InvoiceAnalysis> {
  const form = new FormData();
  form.append("file", file);
  return requestJson("/api/finance/invoices/analyze", {
    method: "POST",
    body: form,
  });
}

export function updateInvoiceLine(
  jobId: string,
  lineId: string,
  changes: InvoiceLineUpdate,
): Promise<InvoiceAnalysis> {
  return requestJson(`/api/finance/invoices/${jobId}/lines/${lineId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}

export function acceptAll(jobId: string): Promise<InvoiceAnalysis> {
  return requestJson(`/api/finance/invoices/${jobId}/accept-all`, {
    method: "POST",
  });
}

export function exportInvoice(
  jobId: string,
  confirmDiscardPending: boolean,
): Promise<Blob> {
  return requestBlob(`/api/finance/invoices/${jobId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      confirm_discard_pending: confirmDiscardPending,
    }),
  });
}

export async function listProviders(): Promise<ProviderSummary[]> {
  const payload = await requestJson<{ providers: ProviderSummary[] }>(
    "/api/finance/providers",
    { cache: "no-store" },
  );
  return payload.providers;
}

export async function getProviderProfile(
  providerId: string,
): Promise<Record<string, unknown>> {
  const payload = await requestJson<{ profile: Record<string, unknown> }>(
    `/api/finance/providers/${providerId}`,
    { cache: "no-store" },
  );
  return payload.profile;
}

export function testProviderProfile(
  profileJson: string,
  sample: File,
): Promise<ProviderTestResult> {
  const form = new FormData();
  form.append("profile_json", profileJson);
  form.append("file", sample);
  return requestJson("/api/finance/providers/test", {
    method: "POST",
    body: form,
  });
}

export function saveProviderProfile(
  profile: Record<string, unknown>,
): Promise<ProviderSummary> {
  return requestJson("/api/finance/providers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
}

export async function registerCurrentUser(): Promise<void> {
  await requestJson("/api/finance/me", { cache: "no-store" });
}

export function getAccessOverview(): Promise<AccessOverview> {
  return requestJson("/api/finance/admin/access-overview", {
    cache: "no-store",
  });
}

