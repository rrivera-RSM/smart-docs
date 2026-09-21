import type {
  AnonymizationResult,
  AnonymizerAnalysis,
  GenerationResult,
  GeneratorAnalysis,
} from "../types";

const configuredBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export function apiUrl(path: string): string {
  return configuredBase + path;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = "No se ha podido completar la operación.";
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail ?? message;
    } catch {
      // Keep a safe generic error when the server did not return JSON.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

async function uploadDocument<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(apiUrl(path), { method: "POST", body });
  return parseResponse<T>(response);
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return parseResponse<T>(response);
}

export const smartDocsApi = {
  analyzeForAnonymization(file: File) {
    return uploadDocument<AnonymizerAnalysis>(
      "/api/anonymizer/analyze",
      file,
    );
  },

  applyAnonymization(
    jobId: string,
    decisions: Array<{ finding_id: string; replacement: string }>,
  ) {
    return postJson<AnonymizationResult>(
      "/api/anonymizer/" + jobId + "/apply",
      { decisions },
    );
  },

  analyzeTemplate(file: File) {
    return uploadDocument<GeneratorAnalysis>("/api/generator/analyze", file);
  },

  repairTemplate(jobId: string) {
    return postJson<GeneratorAnalysis>(
      "/api/generator/" + jobId + "/repair",
    );
  },

  generateDocument(jobId: string, context: Record<string, string>) {
    return postJson<GenerationResult>(
      "/api/generator/" + jobId + "/generate",
      { context },
    );
  },
};
