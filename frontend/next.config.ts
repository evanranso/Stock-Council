import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Plain static files (in out/), so any static host works: Cloudflare Pages, Netlify, Vercel.
  output: "export",
  // Strict mode double-runs effects in dev, which would open two event streams
  // and kick off two (paid) council runs for one page view.
  reactStrictMode: false,
};

export default nextConfig;
