import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://backend:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
