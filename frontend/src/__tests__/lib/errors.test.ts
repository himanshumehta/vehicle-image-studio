import { describe, it, expect } from "vitest";
import { ApiError, NetworkError, isRetryable } from "@/lib/errors";

describe("ApiError", () => {
  it("has correct name", () => {
    const err = new ApiError("test", 404);
    expect(err.name).toBe("ApiError");
  });

  it("stores status", () => {
    const err = new ApiError("test", 500);
    expect(err.status).toBe(500);
  });

  it("stores body", () => {
    const err = new ApiError("test", 400, "bad request");
    expect(err.body).toBe("bad request");
  });

  it("is instance of Error", () => {
    const err = new ApiError("test", 500);
    expect(err).toBeInstanceOf(Error);
  });
});

describe("NetworkError", () => {
  it("has correct name", () => {
    const err = new NetworkError("fail");
    expect(err.name).toBe("NetworkError");
  });

  it("stores cause", () => {
    const cause = new TypeError("fetch failed");
    const err = new NetworkError("fail", cause);
    expect(err.cause).toBe(cause);
  });

  it("is instance of Error", () => {
    const err = new NetworkError("fail");
    expect(err).toBeInstanceOf(Error);
  });
});

describe("isRetryable", () => {
  it("NetworkError is retryable", () => {
    expect(isRetryable(new NetworkError("fail"))).toBe(true);
  });

  it("500 is retryable", () => {
    expect(isRetryable(new ApiError("fail", 500))).toBe(true);
  });

  it("502 is retryable", () => {
    expect(isRetryable(new ApiError("fail", 502))).toBe(true);
  });

  it("429 is retryable", () => {
    expect(isRetryable(new ApiError("fail", 429))).toBe(true);
  });

  it("400 is not retryable", () => {
    expect(isRetryable(new ApiError("fail", 400))).toBe(false);
  });

  it("404 is not retryable", () => {
    expect(isRetryable(new ApiError("fail", 404))).toBe(false);
  });

  it("generic Error is not retryable", () => {
    expect(isRetryable(new Error("fail"))).toBe(false);
  });

  it("null is not retryable", () => {
    expect(isRetryable(null)).toBe(false);
  });
});
