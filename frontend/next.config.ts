import type { NextConfig } from "next";

const backendUrl =
  process.env.BACKEND_URL || "http://localhost:5001";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
