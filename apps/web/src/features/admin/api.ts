import { anonymizerApi } from "../anonymizer/api";
import type { Capability } from "../anonymizer/contract";

const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";

export type HealthResponse = {
  status: string;
  service: string;
};

export type AdminSnapshot = {
  health: HealthResponse;
  capabilities: Capability;
};

async function loadHealth(): Promise<HealthResponse> {
  const response = await fetch(baseUrl + "/api/health", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("La API de SmartDocs no está disponible.");
  }
  return response.json() as Promise<HealthResponse>;
}

export async function loadAdminSnapshot(): Promise<AdminSnapshot> {
  const [health, capabilities] = await Promise.all([
    loadHealth(),
    anonymizerApi.capabilities(),
  ]);
  return { health, capabilities };
}