import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@ai-cio/ui", "@ai-cio/utils", "@ai-cio/contracts"],
};

export default nextConfig;
