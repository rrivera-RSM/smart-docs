import type { NextConfig } from "next";

const apiTarget =
  process.env.SMARTDOCS_API_PROXY_TARGET ?? "http://127.0.0.1:8000";

function publicFlag(publicName: string, serverName: string): string {
  return process.env[publicName] ?? process.env[serverName] ?? "false";
}

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_SMARTDOCS_FEATURE_PDF: publicFlag(
      "NEXT_PUBLIC_SMARTDOCS_FEATURE_PDF",
      "SMARTDOCS_FEATURE_PDF",
    ),
    NEXT_PUBLIC_SMARTDOCS_FEATURE_IMAGE_OCR: publicFlag(
      "NEXT_PUBLIC_SMARTDOCS_FEATURE_IMAGE_OCR",
      "SMARTDOCS_FEATURE_IMAGE_OCR",
    ),
    NEXT_PUBLIC_SMARTDOCS_FEATURE_WEBADMIN: publicFlag(
      "NEXT_PUBLIC_SMARTDOCS_FEATURE_WEBADMIN",
      "SMARTDOCS_FEATURE_WEBADMIN",
    ),
  },
  turbopack: {
    root: process.cwd(),
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
