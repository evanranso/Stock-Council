import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Strict mode double-runs effects in dev, which would open two event streams
  // and kick off two (paid) council runs for one page view.
  reactStrictMode: false,
};

export default nextConfig;
