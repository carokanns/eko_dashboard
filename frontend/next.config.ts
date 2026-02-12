import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  logging: {
    incomingRequests: false,
  },
  allowedDevOrigins: [
    "localhost",
    "127.0.0.1",
    "::1",
    "192.168.*.*",
    "10.*.*.*",
    "172.*.*.*",
  ],
};

export default nextConfig;
