import type { NextConfig } from "next";

// Where the FastAPI backend listens. Read when `next dev` / `next build` starts.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const isDev = process.env.NODE_ENV !== "production";

// Next.js injects inline bootstrap scripts, so script-src needs 'unsafe-inline'
// without a nonce setup; dev mode also needs eval (React Refresh) and a websocket (HMR).
// `https:` in img-src/connect-src is for presigned S3 URLs when STORAGE_BACKEND=s3.
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data: https:",
  "font-src 'self'",
  `connect-src 'self' blob: https:${isDev ? " ws: wss:" : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  reactStrictMode: false,
  devIndicators: false,
  poweredByHeader: false,
  experimental: {
    // Upscaling large images on CPU can take minutes; don't cut the proxy off at 30s.
    proxyTimeout: 10 * 60 * 1000,
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    return [
      {
        // Proxy all /api/* requests to the backend so the browser never needs CORS.
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
