import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow API calls to the FastAPI backend
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },

  // TypeScript and React strict mode
  typescript: {
    ignoreBuildErrors: false,
  },
  reactStrictMode: true,
};

export default nextConfig;
