import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Pin the project root (a lockfile higher up the folder tree can confuse Next).
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
