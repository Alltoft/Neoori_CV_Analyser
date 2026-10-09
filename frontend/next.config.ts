import type { NextConfig } from "next";

const backendUrl =
  process.env.BACKEND_URL || "http://localhost:5001";

const nextConfig: NextConfig = {
  // Docker: emit .next/standalone (self-contained server.js, no node_modules
  // needed at runtime).
  output: "standalone",
  skipTrailingSlashRedirect: true,
  // Dev only. Next refuses its dev resources (the hot-reload socket) to an
  // origin it does not know, and its default `*.localhost` matches one label:
  // neoori.localhost, not cv.neoori.localhost (subdomain split spec,
  // « Frontend »). The dev compose file sets DOMAIN; a production build
  // ignores this key.
  allowedDevOrigins: process.env.DOMAIN ? [`*.${process.env.DOMAIN}`] : [],
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
