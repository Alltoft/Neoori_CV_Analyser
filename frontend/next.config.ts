import type { NextConfig } from "next";

const backendUrl =
  process.env.BACKEND_URL || "http://localhost:5001";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  images: {
    // Next 16 requires non-default next/image quality values to be whitelisted.
    qualities: [75, 92],
  },
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
