import { ApiError, NetworkError, isRetryable } from "./errors";
import type { BrandsResponse, ImageMetadata, ImagesResponse, SavedImage } from "./types";

// Relative URLs: Next.js rewrites proxy /api/* to the backend, so the browser
// never talks to another origin and no CORS is needed.
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 500;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** fetch with exponential backoff on network errors, 429 and 5xx. */
export async function fetchWithRetry(path: string, options?: RequestInit): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    let res: Response;
    try {
      res = await fetch(path, options);
    } catch (e) {
      if (options?.signal?.aborted) throw e;
      if (attempt < MAX_RETRIES) {
        await sleep(RETRY_BASE_MS * 2 ** attempt);
        continue;
      }
      throw new NetworkError("Network request failed", e);
    }
    if (res.ok) return res;
    const err = new ApiError(errorDetail(await res.text(), res.status), res.status);
    if (attempt < MAX_RETRIES && isRetryable(err)) {
      await sleep(RETRY_BASE_MS * 2 ** attempt);
      continue;
    }
    throw err;
  }
}

/** FastAPI errors look like {"detail": "..."}; fall back to the status code. */
function errorDetail(body: string, status: number): string {
  try {
    const detail = JSON.parse(body)?.detail;
    if (typeof detail === "string" && detail) return detail;
  } catch {
    // not JSON
  }
  return `HTTP ${status}`;
}

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  return (await fetchWithRetry(path, options)).json();
}

async function postForBlobUrl(path: string, body: FormData): Promise<string> {
  const res = await fetchWithRetry(path, { method: "POST", body });
  return URL.createObjectURL(await res.blob());
}

// --- Gallery -----------------------------------------------------------------

export async function listImages(prefix = "", maxKeys = 50, continuationToken = "") {
  const params = new URLSearchParams({ prefix, max_keys: String(maxKeys) });
  if (continuationToken) params.set("continuation_token", continuationToken);
  return fetchJSON<ImagesResponse>(`/api/images?${params}`);
}

export async function listBrands() {
  return fetchJSON<BrandsResponse>("/api/images/brands");
}

export async function getImageMetadata(key: string) {
  return fetchJSON<ImageMetadata>(`/api/images/detail/${encodeURIComponent(key)}`);
}

export async function uploadProcessedImage(key: string, blob: Blob) {
  const form = new FormData();
  form.append("key", key);
  form.append("file", blob, "processed.png");
  return fetchJSON<SavedImage>("/api/images/upload", { method: "POST", body: form });
}

export async function importImage(file: File, collection = "uploads") {
  const form = new FormData();
  form.append("file", file);
  form.append("collection", collection);
  return fetchJSON<SavedImage>("/api/images/import", { method: "POST", body: form });
}

export async function deleteImage(key: string) {
  return fetchJSON<{ deleted: string }>(`/api/images/detail/${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
}

/** Walk `pagesNeeded` pages forward from `startToken` and return their continuation tokens. */
export async function fetchPageTokens(
  prefix: string,
  maxKeys: number,
  startToken: string,
  pagesNeeded: number,
): Promise<string[]> {
  const tokens: string[] = [];
  let currentToken = startToken;
  for (let i = 0; i < pagesNeeded; i++) {
    const data = await listImages(prefix, maxKeys, currentToken);
    if (!data.next_token) break;
    tokens.push(data.next_token);
    currentToken = data.next_token;
  }
  return tokens;
}

// --- Processing --------------------------------------------------------------

export type UpscaleFactor = 2 | 4 | 8;

/** Operations that accept either an uploaded image or a storage key. */
export type ProcessEndpoint = "upscale" | "enhance" | "mirror" | "crop" | "watermark";

/** The image to process: the current edited result, or the stored original. */
type ImageSource = { blob: Blob } | { key: string };

export type FormFields = Record<string, string | number | boolean | undefined>;

/** POST an image to /api/process/<endpoint>; returns an object URL for the PNG result. */
export async function processImage(
  endpoint: ProcessEndpoint,
  source: ImageSource,
  fields: FormFields = {},
): Promise<string> {
  const form = new FormData();
  if ("blob" in source) form.append("file", source.blob, "image.png");
  else form.append("key", source.key);
  for (const [name, value] of Object.entries(fields)) {
    if (value !== undefined) form.append(name, String(value));
  }
  return postForBlobUrl(`/api/process/${endpoint}`, form);
}

export async function removeBackground(key: string): Promise<string> {
  const form = new FormData();
  form.append("key", key);
  return postForBlobUrl("/api/process/remove-background", form);
}

/** Cut out the vehicle and place it on the white studio backdrop, or on `background` if given. */
export async function compositeBackground(key: string, background?: File): Promise<string> {
  const form = new FormData();
  form.append("key", key);
  if (background) form.append("template_file", background);
  return postForBlobUrl("/api/process/composite-template", form);
}

// --- AI clean-up (optional, needs an API key on the server) -------------------

export async function llmEditImage(
  imageBlob: Blob,
  instruction: { prompt?: string; preset?: string },
  options?: {
    provider?: "openai" | "gemini";
    quality?: "low" | "medium" | "high";
  },
  signal?: AbortSignal,
): Promise<Blob> {
  const form = new FormData();
  form.append("file", imageBlob, "image.png");
  if (instruction.preset) form.append("preset", instruction.preset);
  if (instruction.prompt) form.append("prompt", instruction.prompt);
  if (options?.provider) form.append("provider", options.provider);
  form.append("quality", options?.quality ?? "medium");

  // No retries: every call is billed by the provider.
  const res = await fetch("/api/process/llm-edit", { method: "POST", body: form, signal });
  if (!res.ok) {
    throw new Error(errorDetail(await res.text(), res.status).replace(/^HTTP /, "AI edit failed: HTTP "));
  }
  return res.blob();
}

export async function getEditProviders() {
  return fetchJSON<{
    providers: Array<{ name: string; available: boolean; models: string[] }>;
  }>("/api/process/llm-edit/providers");
}
