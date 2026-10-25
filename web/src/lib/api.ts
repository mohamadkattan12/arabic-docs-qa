import { parseSSE } from "./sse";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Required by the API on document changes (blocks cross-site form posts).
const APP_HEADER = { "X-Requested-By": "arabic-docs-qa" };

export type Citation = { document: string; location: string; quote: string };

export type Done = {
  answerable: boolean;
  citations: Citation[];
  refused: boolean;
  truncated: boolean;
  model: string;
  text: string;
};

export type DocumentRow = {
  id: string;
  name: string;
  lang: "ar" | "en";
  chunks: number;
  created_at: string;
};

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // not JSON
  }
  return `Request failed (${response.status}).`;
}

/** POST /ask and read the Server-Sent Events stream: delta events, then done or error. */
export async function ask(
  question: string,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<Done> {
  const response = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok || !response.body) throw new Error(await errorMessage(response));

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const parsed = parseSSE(buffer + value);
    buffer = parsed.rest;
    for (const { event, data } of parsed.events) {
      const payload = JSON.parse(data);
      if (event === "delta") onDelta(payload.text);
      else if (event === "done") return payload as Done;
      else if (event === "error") throw new Error(payload.message);
    }
  }
  throw new Error("The answer stream ended unexpectedly.");
}

export async function listDocuments(): Promise<DocumentRow[]> {
  const response = await fetch(`${API_URL}/documents`);
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

export async function uploadDocument(file: File): Promise<{ created: boolean; name: string }> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_URL}/documents`, {
    method: "POST",
    headers: APP_HEADER,
    body,
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const response = await fetch(`${API_URL}/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: APP_HEADER,
  });
  if (!response.ok) throw new Error(await errorMessage(response));
}

/** Latest eval result, or null when none has been run yet. */
export async function latestEval(): Promise<EvalResult | null> {
  const response = await fetch(`${API_URL}/eval/latest`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

export type ModelSummary = {
  answer_score: number | null;
  citation_accuracy: number | null;
  refusal_accuracy: number | null;
  false_refusal_rate: number | null;
  injection_resisted: number | null;
  language_match: number | null;
  cost_per_100_usd: number | null;
  median_latency_s: number | null;
};

export type EvalResult = {
  created_at: string;
  dataset_size: number;
  embedding_model: string;
  retrieval_mode: string;
  judge_model: string;
  effort: string;
  recommended: string | null;
  pdf_word_recall: number;
  models: Record<string, ModelSummary>;
  retrieval: Record<
    string,
    { hit_at_6: number | null; same_language: number | null; cross_language: number | null }
  >;
};
