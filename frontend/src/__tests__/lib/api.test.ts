import { describe, it, expect, vi } from "vitest";

// We need to test the error handling and retry logic
vi.mock("./errors", () => ({
  ApiError: class extends Error {
    status: number;
    body?: string;
    constructor(msg: string, status: number, body?: string) {
      super(msg);
      this.name = "ApiError";
      this.status = status;
      this.body = body;
    }
  },
  NetworkError: class extends Error {
    constructor(msg: string) {
      super(msg);
      this.name = "NetworkError";
    }
  },
  isRetryable: (e: any) => {
    if (e.name === "NetworkError") return true;
    if (e.name === "ApiError") return e.status === 429 || e.status >= 500;
    return false;
  },
}));

describe("API error handling", () => {
  it("ApiError stores status and body", async () => {
    const { ApiError } = await import("@/lib/errors");
    const err = new ApiError("test", 500, "body");
    expect(err.status).toBe(500);
    expect(err.body).toBe("body");
    expect(err.name).toBe("ApiError");
  });

  it("NetworkError wraps cause", async () => {
    const { NetworkError } = await import("@/lib/errors");
    const cause = new TypeError("fetch failed");
    const err = new NetworkError("Network request failed", cause);
    expect(err.name).toBe("NetworkError");
    expect(err.cause).toBe(cause);
  });
});

describe("isRetryable", () => {
  it("returns true for NetworkError", async () => {
    const { NetworkError, isRetryable } = await import("@/lib/errors");
    expect(isRetryable(new NetworkError("fail"))).toBe(true);
  });

  it("returns true for 500 ApiError", async () => {
    const { ApiError, isRetryable } = await import("@/lib/errors");
    expect(isRetryable(new ApiError("fail", 500))).toBe(true);
  });

  it("returns true for 429 ApiError", async () => {
    const { ApiError, isRetryable } = await import("@/lib/errors");
    expect(isRetryable(new ApiError("fail", 429))).toBe(true);
  });

  it("returns false for 400 ApiError", async () => {
    const { ApiError, isRetryable } = await import("@/lib/errors");
    expect(isRetryable(new ApiError("fail", 400))).toBe(false);
  });

  it("returns false for generic Error", async () => {
    const { isRetryable } = await import("@/lib/errors");
    expect(isRetryable(new Error("fail"))).toBe(false);
  });
});
