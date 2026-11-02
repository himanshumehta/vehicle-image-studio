export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(message: string, public cause?: unknown) {
    super(message);
    this.name = "NetworkError";
  }
}

export function isRetryable(error: unknown): boolean {
  if (error instanceof NetworkError) return true;
  if (error instanceof ApiError) {
    return error.status === 429 || error.status >= 500;
  }
  return false;
}
