import type {
  AnalysisOptions,
  AnonymizerJob,
  Capability,
  GroupDecision,
  ManualFinding,
} from "./contract";

const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";

export class AnonymizerApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = "No se ha podido completar la operación.";
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail ?? message;
    } catch {
      // The API may return an empty response for transport-level errors.
    }
    throw new AnonymizerApiError(message, response.status);
  }
  return (await response.json()) as T;
}

async function json<T>(path: string, method: string, body?: unknown): Promise<T> {
  return parse<T>(
    await fetch(baseUrl + path, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    }),
  );
}

export const anonymizerApi = {
  downloadUrl(path: string) {
    return baseUrl + path;
  },

  capabilities() {
    return json<Capability>("/api/anonymizer/capabilities", "GET");
  },

  async analyze(file: File, options: AnalysisOptions) {
    const body = new FormData();
    body.append("file", file);
    body.append("options", JSON.stringify(options));
    return parse<AnonymizerJob>(
      await fetch(baseUrl + "/api/anonymizer/analyze", { method: "POST", body }),
    );
  },

  get(jobId: string) {
    return json<AnonymizerJob>(`/api/anonymizer/${jobId}`, "GET");
  },

  addManual(jobId: string, finding: ManualFinding) {
    return json<AnonymizerJob>(
      `/api/anonymizer/${jobId}/findings/manual`,
      "POST",
      finding,
    );
  },

  apply(
    jobId: string,
    decisions: GroupDecision[],
    removeUnsupportedContent: boolean,
  ) {
    return json<AnonymizerJob>(`/api/anonymizer/${jobId}/apply`, "POST", {
      decisions,
      review_confirmed: true,
      remove_unsupported_content: removeUnsupportedContent,
    });
  },

  async remove(jobId: string) {
    const response = await fetch(baseUrl + `/api/anonymizer/${jobId}`, {
      method: "DELETE",
    });
    if (!response.ok && response.status !== 404) await parse(response);
  },
};
