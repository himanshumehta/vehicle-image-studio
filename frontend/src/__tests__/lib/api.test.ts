import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchWithRetry, processImage, compositeBackground } from "@/lib/api";
import { ApiError } from "@/lib/errors";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("URL", { ...globalThis.URL, createObjectURL: vi.fn(() => "blob:result") });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const ok = () => new Response(new Blob(["png"]), { status: 200 });
const fail = (status: number, detail = "nope") =>
  new Response(JSON.stringify({ detail }), { status, headers: { "Content-Type": "application/json" } });

describe("fetchWithRetry", () => {
  it("retries 503 with backoff and then succeeds", async () => {
    fetchMock.mockResolvedValueOnce(fail(503, "busy")).mockResolvedValueOnce(ok());
    const pending = fetchWithRetry("/api/x");
    await vi.runAllTimersAsync();
    await expect(pending).resolves.toBeInstanceOf(Response);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a 400 and surfaces the server's detail message", async () => {
    fetchMock.mockResolvedValue(fail(400, "Unsupported image type"));
    const err = await fetchWithRetry("/api/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.message).toBe("Unsupported image type");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("gives up after the retry budget", async () => {
    fetchMock.mockImplementation(async () => fail(500));
    const pending = fetchWithRetry("/api/x").catch((e) => e);
    await vi.runAllTimersAsync();
    const err = await pending;
    expect(err.status).toBe(500);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});

describe("processImage", () => {
  it("sends a storage key and the extra fields as multipart form data", async () => {
    fetchMock.mockResolvedValue(ok());
    const url = await processImage("upscale", { key: "vehicles/a.png" }, { scale: 4, unset: undefined });
    expect(url).toBe("blob:result");
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/process/upscale");
    const form = init.body as FormData;
    expect(form.get("key")).toBe("vehicles/a.png");
    expect(form.get("scale")).toBe("4");
    expect(form.has("unset")).toBe(false);
    expect(form.has("file")).toBe(false);
  });

  it("sends the current result as a file upload", async () => {
    fetchMock.mockResolvedValue(ok());
    await processImage("mirror", { blob: new Blob(["x"], { type: "image/png" }) });
    const form = fetchMock.mock.calls[0][1].body as FormData;
    expect(form.get("file")).toBeInstanceOf(Blob);
    expect(form.has("key")).toBe(false);
  });
});

describe("compositeBackground", () => {
  it("only attaches a background file when one is given", async () => {
    fetchMock.mockResolvedValue(ok());
    await compositeBackground("vehicles/a.png");
    const form = fetchMock.mock.calls[0][1].body as FormData;
    expect(form.get("key")).toBe("vehicles/a.png");
    expect(form.has("template_file")).toBe(false);
  });
});
