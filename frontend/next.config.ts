import type { NextConfig } from "next";

// 정적 export: FastAPI 가 frontend/out 을 같은 도메인에서 서빙한다 (Railway 단일 서비스).
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
