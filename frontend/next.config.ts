import type { NextConfig } from "next";

// Where the FastAPI backend listens. Read when `next dev` / `next build` starts.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  devIndicators: false,
  experimental: {
    // Upscaling large images on CPU can take minutes; don't cut the proxy off at 30s.
    proxyTimeout: 10 * 60 * 1000,
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
