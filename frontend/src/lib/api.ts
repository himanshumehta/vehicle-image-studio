import { ApiError, NetworkError, isRetryable } from "./errors";

// Use relative URLs — Next.js rewrites proxy /api/* to the backend.
// This avoids CORS issues regardless of which port the dev server runs on.
const API_BASE = "";
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 500;

async function fetchWithRetry(path: string, options?: RequestInit): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, options);
      if (!res.ok) {
        const body = await res.text();
        const err = new ApiError(`HTTP ${res.status}`, res.status, body);
        if (attempt < MAX_RETRIES && isRetryable(err)) {
          lastError = err;
          await new Promise((r) => setTimeout(r, RETRY_BASE_MS * 2 ** attempt));
          continue;
        }
        throw err;
      }
      return res;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      const netErr = new NetworkError("Network request failed", e);
      if (attempt < MAX_RETRIES) {
        lastError = netErr;
        await new Promise((r) => setTimeout(r, RETRY_BASE_MS * 2 ** attempt));
        continue;
      }
      throw netErr;
    }
  }
  throw lastError;
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetchWithRetry(path, options);
  return res!.json();
}

async function fetchBlob(path: string, options?: RequestInit): Promise<Blob> {
  const res = await fetchWithRetry(path, options);
  return res!.blob();
}

export async function listImages(prefix = "", maxKeys = 50, continuationToken = "") {
  let url = `/api/images?prefix=${encodeURIComponent(prefix)}&max_keys=${maxKeys}`;
  if (continuationToken) {
    url += `&continuation_token=${encodeURIComponent(continuationToken)}`;
  }
  return fetchAPI<{
    images: Array<{ key: string; size: number; last_modified: string; url: string }>;
    count: number;
    next_token: string;
  }>(url);
}

export async function listBrands() {
  return fetchAPI<{
    brands: Array<{ slug: string; name: string; prefix: string; image_count: number }>;
    total_brands: number;
    total_images: number;
  }>("/api/images/brands");
}

export async function getImageMetadata(key: string) {
  return fetchAPI<{ key: string; size: number; content_type: string; last_modified: string; url: string }>(
    `/api/images/detail/${encodeURIComponent(key)}`
  );
}

export async function removeBackground(key: string): Promise<string> {
  const blob = await fetchBlob("/api/process/remove-background", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
  return URL.createObjectURL(blob);
}

export async function uploadProcessedImage(key: string, blob: Blob) {
  const formData = new FormData();
  formData.append("key", key);
  formData.append("file", blob, "processed.png");
  return fetchAPI<{ key: string; url: string; size: number }>("/api/images/upload", {
    method: "POST",
    body: formData,
  });
}

export async function importImage(file: File, collection = "uploads") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("collection", collection);
  return fetchAPI<{ key: string; url: string; size: number }>("/api/images/import", {
    method: "POST",
    body: formData,
  });
}

export async function deleteImage(key: string) {
  return fetchAPI<{ deleted: string }>(`/api/images/detail/${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
}

export async function mirrorImageBlob(imageBlob: Blob): Promise<string> {
  const formData = new FormData();
  formData.append("file", imageBlob, "image.png");
  const blob = await fetchBlob("/api/process/mirror", {
    method: "POST",
    body: formData,
  });
  return URL.createObjectURL(blob);
}

export async function mirrorImageKey(key: string): Promise<string> {
  const formData = new FormData();
  formData.append("key", key);
  const blob = await fetchBlob("/api/process/mirror", {
    method: "POST",
    body: formData,
  });
  return URL.createObjectURL(blob);
}

export async function cropImageBlob(imageBlob: Blob, x: number, y: number, w: number, h: number): Promise<string> {
  const formData = new FormData();
  formData.append("file", imageBlob, "image.png");
  formData.append("crop_x", String(x));
  formData.append("crop_y", String(y));
  formData.append("crop_w", String(w));
  formData.append("crop_h", String(h));
  const blob = await fetchBlob("/api/process/crop", {
    method: "POST",
    body: formData,
  });
  return URL.createObjectURL(blob);
}

export async function cropImageKey(key: string, x: number, y: number, w: number, h: number): Promise<string> {
  const formData = new FormData();
  formData.append("key", key);
  formData.append("crop_x", String(x));
  formData.append("crop_y", String(y));
  formData.append("crop_w", String(w));
  formData.append("crop_h", String(h));
  const blob = await fetchBlob("/api/process/crop", {
    method: "POST",
    body: formData,
  });
  return URL.createObjectURL(blob);
}

export async function enhanceImageBlob(imageBlob: Blob): Promise<string> {
  const formData = new FormData();
  formData.append("file", imageBlob, "image.png");
  const blob = await fetchBlob("/api/process/enhance", {
    method: "POST",
    body: formData,
  });
  return URL.createObjectURL(blob);
}

export async function enhanceImageKey(key: string): Promise<string> {
  const formData = new FormData();
  formData.append("key", key);
  const blob = await fetchBlob("/api/process/enhance", {
    method: "POST",
    body: formData,
  });
  return URL.createObjectURL(blob);
}

export type UpscaleFactor = 2 | 4 | 8;

export async function upscaleImageBlob(imageBlob: Blob, scale: UpscaleFactor): Promise<string> {
  const formData = new FormData();
  formData.append("file", imageBlob, "image.png");
  formData.append("scale", String(scale));
  const blob = await fetchBlob("/api/process/upscale", { method: "POST", body: formData });
  return URL.createObjectURL(blob);
}

export async function upscaleImageKey(key: string, scale: UpscaleFactor): Promise<string> {
  const formData = new FormData();
  formData.append("key", key);
  formData.append("scale", String(scale));
  const blob = await fetchBlob("/api/process/upscale", { method: "POST", body: formData });
  return URL.createObjectURL(blob);
}

export async function compositeWithTemplate(key: string, templateId: string): Promise<string> {
  const formData = new FormData();
  formData.append("key", key);
  formData.append("template", templateId);
  const blob = await fetchBlob("/api/process/composite-template", {
    method: "POST",
    body: formData,
  });
  return URL.createObjectURL(blob);
}

export async function compositeWithCustomFile(key: string, file: File): Promise<string> {
  const formData = new FormData();
  formData.append("key", key);
  formData.append("template_file", file);
  const blob = await fetchBlob("/api/process/composite-template", {
    method: "POST",
    body: formData,
  });
  return URL.createObjectURL(blob);
}

export async function healthCheck() {
  return fetchAPI<{
    status: string;
    bg_model: string;
    bg_model_loaded: boolean;
    upscaler_loaded: boolean;
  }>("/api/process/health");
}

// --- Watermark ---

export async function watermarkImage(
  imageBlob: Blob,
  options: {
    text: string;
    position?: string;
    opacity?: number;
    fontSize?: number;
    color?: string;
    repeat?: boolean;
  },
): Promise<string> {
  const form = new FormData();
  form.append("file", imageBlob, "image.png");
  form.append("text", options.text);
  if (options.position) form.append("position", options.position);
  if (options.opacity !== undefined) form.append("opacity", String(options.opacity));
  if (options.fontSize !== undefined) form.append("font_size", String(options.fontSize));
  if (options.color) form.append("color", options.color);
  if (options.repeat) form.append("repeat", "true");
  const blob = await fetchBlob("/api/process/watermark", {
    method: "POST",
    body: form,
  });
  return URL.createObjectURL(blob);
}

export async function watermarkImageKey(
  key: string,
  options: {
    text: string;
    position?: string;
    opacity?: number;
    fontSize?: number;
    color?: string;
    repeat?: boolean;
  },
): Promise<string> {
  const form = new FormData();
  form.append("key", key);
  form.append("text", options.text);
  if (options.position) form.append("position", options.position);
  if (options.opacity !== undefined) form.append("opacity", String(options.opacity));
  if (options.fontSize !== undefined) form.append("font_size", String(options.fontSize));
  if (options.color) form.append("color", options.color);
  if (options.repeat) form.append("repeat", "true");
  const blob = await fetchBlob("/api/process/watermark", {
    method: "POST",
    body: form,
  });
  return URL.createObjectURL(blob);
}

// --- LLM Image Editing ---

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

  const res = await fetch("/api/process/llm-edit", {
    method: "POST",
    body: form,
    signal,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "AI edit failed" }));
    throw new Error(err.detail || `AI edit failed (${res.status})`);
  }

  return res.blob();
}

export async function getEditPresets() {
  return fetchAPI<Array<{ id: string; label: string; prompt: string }>>("/api/process/llm-edit/presets");
}

export async function getEditProviders() {
  return fetchAPI<{
    providers: Array<{ name: string; available: boolean; models: string[] }>;
  }>("/api/process/llm-edit/providers");
}

export async function fetchPageTokens(
  prefix: string,
  maxKeys: number,
  startToken: string,
  pagesNeeded: number
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
