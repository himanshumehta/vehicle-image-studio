# Security policy

## Reporting a vulnerability

Email **mehta.august@gmail.com** with a description, the affected file or endpoint, and steps to reproduce. Please do not open a public issue for a vulnerability. You should get a reply within a week. Fixes land on `main`; there are no release branches.

## Supported versions

Only `main` is supported.

## What this project is

A single-user image-editing tool meant to run on your own machine: a FastAPI service (`backend/`), a Next.js UI that proxies to it (`frontend/`) and a CLI. **It has no authentication.** Anyone who can reach the API can read, overwrite and delete images in its store and, if an AI provider key is configured, spend money on that provider. Do not expose it on a network you do not trust, and put it behind an authenticating reverse proxy if you deploy it anywhere shared.

## Threats it does defend against

| Threat | Control | Where |
|---|---|---|
| A web page you visit POSTs to `localhost:8000` (CSRF-style; multipart forms skip CORS preflight) | State-changing requests that the browser marks `Sec-Fetch-Site: cross-site`, or whose `Origin` does not match, get 403 unless the origin is in `CORS_ORIGINS` | `backend/http_security.py` |
| DNS rebinding (a hostile domain resolved to 127.0.0.1) | `Host` must be in `ALLOWED_HOSTS` (default `localhost,127.0.0.1`) | `backend/main.py` |
| Path traversal through storage keys | Keys must be relative, have no `.`/`..` segments, no backslashes, and end in an image extension; local paths are re-checked after `resolve()` | `backend/services/storage.py` |
| Stored XSS via the file server | Only `.jpg/.jpeg/.png/.webp` keys can be written or served; uploads must decode as JPEG/PNG/WebP; API responses carry `nosniff` and `Content-Security-Policy: default-src 'none'; sandbox` | `routers/images.py`, `http_security.py` |
| Oversized bodies and decompression bombs | 25 MB per image, 51 MB per request (checked before parsing, also for chunked bodies); 40 MP decode limit checked from the header; Pillow's bomb warning is an error | `http_security.py`, `utils/image_helpers.py` |
| CPU/RAM exhaustion by heavy jobs | Model jobs run in worker threads behind a concurrency limit (`MAX_CONCURRENT_JOBS`, 503 + `Retry-After` when full); upscaling is refused when the network output would exceed `MAX_UPSCALE_OUTPUT_PIXELS` | `services/jobs.py`, `services/upscale_service.py` |
| Leaking paths or provider errors to clients | Unexpected failures return a generic message; details go to the server log | `routers/processing.py`, `image_edit_providers/base.py` |
| Tampered model weights | Real-ESRGAN `.pth` and `u2net.onnx` are checked against pinned SHA-256 digests; `torch.load(weights_only=True)`; the two Hugging Face models that need `trust_remote_code` are pinned to a commit | `scripts/download_models.py`, `services/background_removal.py` |
| Hung calls to paid AI providers | 120 s client timeout, one retry, prompts capped at 2,000 characters | `image_edit_providers/` |
| Supply chain | Direct dependencies pinned or bounded; CI runs `pip-audit`, `npm audit`, Bandit and Gitleaks; Actions pinned to commit SHAs; Dependabot weekly | `.github/` |

The UI sets a Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff` and a restrictive `Permissions-Policy` (`frontend/next.config.ts`). The policy still allows inline scripts because Next.js injects them without a nonce in this setup.

## Out of scope

- Anything that requires access to the machine or the `.env` file.
- Denial of service by a client that is already allowed to use the API (there is no per-client rate limit, only the global job limit).
- What the OpenAI or Gemini APIs do with images sent to them, and the content of their outputs. AI clean-up is off unless you set a key.
- Vulnerabilities in model weights or in the Hugging Face repositories themselves beyond the pinning described above.
